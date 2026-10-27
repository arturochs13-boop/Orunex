with open('src/main_av.py','r',encoding='utf-8',errors='ignore') as f:
    lines=f.readlines()
kws=['settings','config','integ','show_panel','navigator','navbar','menu']
results=[]
for i,l in enumerate(lines):
    ll=l.lower()
    if any(k in ll for k in kws):
        results.append(f'{i+1:5}: {l.rstrip()[:100]}')
with open('tmp_scan_out.txt','w',encoding='utf-8') as o:
    o.write('\n'.join(results[:120]))
print(f'Done. {len(results)} matches.')
