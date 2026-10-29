"""Independent check. Recomputes every dashboard dataset with pandas straight from the raw monthly
files (no SQL, no DuckDB) and compares it with the SQL results. Differences of 0.05 or less are rounding.
Run after build.py and export_dashboard_data.py."""
import pandas as pd, numpy as np, glob
import pathlib
ROOT=pathlib.Path(__file__).resolve().parent
D=str(ROOT/'dashboard_data')+'/'
fs=sorted(glob.glob(str(ROOT/'data'/'raw'/'311_*.csv.gz')))
raw=pd.concat([pd.read_csv(f,dtype=str,usecols=['unique_key','created_date','closed_date','agency','complaint_type','borough']) for f in fs],ignore_index=True)
print('raw rows',len(raw),'unique keys',raw.unique_key.nunique())
raw['created']=pd.to_datetime(raw.created_date); raw['closed']=pd.to_datetime(raw.closed_date)
raw['hrs']=(raw.closed-raw.created).dt.total_seconds()/3600
raw['complaint']=raw.agency+' - '+raw.complaint_type
raw['borough']=raw.borough.where(raw.borough!='Unspecified')
snap=pd.Timestamp('2026-10-26')
df=raw[(raw.hrs.isna()|(raw.hrs>=0))&(raw.closed.isna()|(raw.closed<=snap))].copy()
df['is_closed']=df.closed.notna(); df['zero']=df.hrs==0
df['c90']=df.created<pd.Timestamp('2026-08-01'); df['c6']=df.created<pd.Timestamp('2026-04-01')
print('window',df.created.min(),df.created.max())
bad=[]
def cmp(name,a,b,tol=0.051):
    a=pd.to_numeric(a); b=pd.to_numeric(b)
    d=(a.values-b.values); m=np.nanmax(np.abs(d)) if len(d) else 0
    print(f'{name:38s} max abs diff {m:.4f}', '' if m<=tol else '  <<<<< MISMATCH'); 
    if m>tol: bad.append(name)
# headline
h=pd.read_csv(D+'headline.csv').iloc[0]
c9=df[df.c90]
print('total',len(df),h.total_requests,'| dropped',len(raw)-len(df),h.dropped_impossible,'| noclose',(~df.is_closed).sum(),h.no_close_total,'| zero',df.zero.sum(),h.same_second_closures)
print('NYPD med',round(c9[c9.agency=='NYPD'].hrs.median(),1),h.nypd_median_hrs,'| HPD med',round(c9[c9.agency=='HPD'].hrs.median(),1),h.hpd_median_hrs)
cc=c9[c9.is_closed]
print('HPD req share (closed)',round(100*(cc.agency=='HPD').mean(),1),h.hpd_request_share_pct,'| wait share',round(100*cc[cc.agency=='HPD'].hrs.sum()/cc.hrs.sum(),1),h.hpd_wait_share_pct)
b6=df[df.c6&~df.is_closed]; print('backlog',len(b6),h.backlog_6m,'| top10 %',round(100*b6.complaint.value_counts().head(10).sum()/len(b6),1),h.backlog_top10_pct)
vol=df.agency.value_counts(normalize=True).head(3).mul(100).round(1); print('top3',vol.sum().round(1),h.top3_agency_pct)
# agencies
ag=pd.read_csv(D+'agencies.csv')
g=c9.groupby('agency').hrs
t=pd.DataFrame({'req':df.groupby('agency').size(),'med':g.median(),'p90':g.quantile(.9),
  'nd7':c9.groupby('agency').apply(lambda x:100*((x.hrs>168)|x.hrs.isna()).mean())}).loc[ag.agency]
cmp('agencies.requests',ag.requests,t.req,0); cmp('agencies.median',ag.median_hrs,t['med']); cmp('agencies.p90',ag.p90_hrs,t.p90); cmp('agencies.not_done_7d',ag.pct_not_done_7d,t.nd7)
# complaints
cp=pd.read_csv(D+'complaints.csv')
gc=c9.groupby('complaint')
wd=cc.groupby('complaint').hrs.sum()/24; 
t=pd.DataFrame({'req':gc.size(),'med':gc.hrs.median(),'p90':gc.hrs.quantile(.9),'nd':gc.apply(lambda x:100*((x.hrs>168)|x.hrs.isna()).mean())}).loc[cp.complaint]
cmp('complaints.requests',cp.requests,t.req,0); cmp('complaints.median',cp.median_hrs,t['med']); cmp('complaints.p90',cp.p90_hrs,t.p90); cmp('complaints.not_done',cp.pct_not_done_7d,t.nd)
cmp('complaints.waiting_share',cp.pct_of_all_waiting,(100*wd/wd.sum()).loc[cp.complaint])
print('complaint types in table',len(cp),'min requests',cp.requests.min())
# boroughs
pops={'BRONX':1406332,'BROOKLYN':2653963,'MANHATTAN':1664862,'QUEENS':2358182,'STATEN ISLAND':501290}
bo=pd.read_csv(D+'boroughs.csv'); bo['K']=bo.borough.str.upper()
bq=df[df.borough.notna()].groupby('borough').size()
cmp('boroughs.requests',bo.requests,bq.loc[bo.K],0)
cmp('boroughs.pct_requests',bo.pct_of_requests,(100*bq/bq.sum()).loc[bo.K])
cmp('boroughs.pct_pop',bo.pct_of_population,pd.Series({k:100*v/sum(pops.values()) for k,v in pops.items()}).loc[bo.K])
nz=c9[c9.is_closed&~c9.zero&c9.borough.notna()]
cmp('boroughs.raw_median',bo.raw_median_hrs,nz.groupby('borough').hrs.median().loc[bo.K])
cmp('boroughs.nypd_share',bo.nypd_share_pct,(100*nz.groupby('borough').apply(lambda x:(x.agency=='NYPD').mean())).loc[bo.K])
cmp('boroughs.hpd_dob_share',bo.hpd_dob_share_pct,(100*nz.groupby('borough').apply(lambda x:x.agency.isin(['HPD','DOB']).mean())).loc[bo.K])
def index(frame):
    cn=frame.groupby('complaint').hrs.agg(['size','median']); cn=cn[(cn['size']>=2000)&(cn['median']>0)]
    x=frame[frame.complaint.isin(cn.index)].groupby(['borough','complaint']).hrs.agg(['size','median']).reset_index()
    x=x[x['size']>=300]; x['city']=x.complaint.map(cn['median']); x['ratio']=x['median']/x.city
    return x
x=index(nz); idx=x.groupby('borough').apply(lambda g:(g.ratio*g['size']).sum()/g['size'].sum())
cmp('boroughs.adjusted_index',bo.adjusted_index,idx.loc[bo.K],0.0051)
x0=index(c9[c9.is_closed&c9.borough.notna()]); i0=x0.groupby('borough').apply(lambda g:(g.ratio*g['size']).sum()/g['size'].sum())
cmp('boroughs.index_with_zero',bo.adjusted_index_with_zero,i0.loc[bo.K],0.0051)
# borough x complaint
bc=pd.read_csv(D+'borough_complaint.csv'); bc['K']=bc.borough.str.upper()
m=bc.merge(x,left_on=['K','complaint'],right_on=['borough','complaint'],how='left',suffixes=('','_p'))
print('borough_complaint rows',len(bc),'| rows in pandas',len(x),'| unmatched',m['size'].isna().sum())
cmp('borough_complaint.requests',m.requests,m['size'],0); cmp('borough_complaint.median',m.median_hrs,m['median']); cmp('borough_complaint.ratio',m.ratio_to_city,m.ratio,0.0051)
hc=bc[(bc.complaint=='DOT - Street Condition')].set_index('borough').median_hrs; print('street bronx/queens',round(hc['Bronx']/hc['Queens'],2),h.street_bronx_vs_queens_x)
hc=bc[(bc.complaint=='DEP - Water System')].set_index('borough').median_hrs; print('water bronx/queens',round(hc['Bronx']/hc['Queens'],2),h.water_bronx_vs_queens_x)
# daily / heat / surge
dd=cc.assign(d=cc.created.dt.date).groupby(['complaint','d']).hrs.agg(vol='size',med='median').reset_index(); dd=dd[dd.vol>=20]
ht=dd[dd.complaint=='HPD - HEAT/HOT WATER'].sort_values('d').reset_index(drop=True)
hd=pd.read_csv(D+'heat_daily.csv'); print('heat days',len(hd),len(ht))
cmp('heat_daily.vol',hd.vol,ht.vol,0); cmp('heat_daily.med',hd.med_hrs,ht.med); cmp('heat_daily.med7',hd.med_hrs_7d_avg,ht.med.rolling(7,min_periods=1).mean()); cmp('heat_daily.vol7',hd.vol_7d_avg,ht.vol.rolling(7,min_periods=1).mean(),0.51)
hq=pd.read_csv(D+'heat_quartiles.csv'); s=ht.sort_values('vol'); parts=np.array_split(np.arange(len(s)),4)
pm=[s.med.iloc[p].median() for p in parts]; cmp('heat_quartiles.median',hq.median_wait_hrs,pd.Series(pm)); print('quartile medians',[round(v,1) for v in pm],'| ratio busiest/quietest',round(pm[3]/pm[0],3))
sg=pd.read_csv(D+'surge.csv'); top12=df.complaint.value_counts().head(12).index
res={}
for c,gp in dd.groupby('complaint'):
    if c in top12 and len(gp)>=60: res[c]=(len(gp),gp.vol.rank(method='min').corr(gp.med.rank(method='min')),gp.vol.median(),gp.vol.max())
r=pd.DataFrame(res,index=['days','sp','mv','pv']).T
print('surge complaint types',len(sg),len(r)); cmp('surge.spearman',sg.spearman,r.sp.loc[sg.complaint],0.0051); cmp('surge.days',sg.days,r.days.loc[sg.complaint],0)
# open
oa=pd.read_csv(D+'open_agency.csv'); c6=df[df.c6]
t=c6.groupby('agency').agg(n=('is_closed','size'),o=('is_closed',lambda s:(~s).sum())).loc[oa.agency]
cmp('open_agency.requests',oa.requests,t.n,0); cmp('open_agency.still_open',oa.still_open,t.o,0)
oc=pd.read_csv(D+'open_complaint.csv'); t=c6.groupby('complaint').agg(n=('is_closed','size'),o=('is_closed',lambda s:(~s).sum()))
cmp('open_complaint.still_open',oc.still_open,t.o.loc[oc.complaint],0); cmp('open_complaint.pct',oc.pct_still_open,(100*t.o/t.n).loc[oc.complaint])
cmp('open_complaint.share_of_backlog',oc.pct_of_backlog,(100*t.o/t.o.sum()).loc[oc.complaint]); print('top10 are the top10 by count:', set(oc.complaint)==set(t.o.nlargest(10).index))
# extra: zero-duration influence on headline medians
for a in ['NYPD','HPD']:
    z=c9[(c9.agency==a)&c9.is_closed]; print(a,'share same-second',round(100*z.zero.mean(),1),'% | median incl',round(z.hrs.median(),2),'excl',round(z[~z.zero].hrs.median(),2))
print('MISMATCHES:',bad)
