"""Explicit shop coordinates and obstacle-aware orthogonal research paths."""
from research_edges import research_edges


def layout(tree,index,economy):
    items=[]
    for column in tree['columns']:
        for node in column['nodes']:
            first=node['units'][0];flags=tree['flags'][first]
            pos=flags.get('rankPosXY')
            if not isinstance(pos,list) or len(pos)!=2 or any(not isinstance(v,int) or v<1 for v in pos):
                raise ValueError(f'Missing/invalid helicopter coordinate: {tree["id"]}/{first}')
            items.append((node,index['records'][first]['rank'],*pos))
    columns=max(x for n,r,x,y in items)
    special=[x for n,r,x,y in items if all(tree['flags'][u].get('reqAir')=='' or tree['flags'][u].get('isClanVehicle') or economy[u].get('costGold',0)>0 for u in n['units'])]
    split=min(special)-1 if special else columns;gap=18 if special else 0
    nodes=[];ranks=[];occupied=set();top=30
    for rank in tree['ranks']:
        rows=max(y for n,r,x,y in items if r==rank);height=30+rows*90
        ranks.append({'rank':rank,'top':top,'height':height})
        for node,r,x,y in items:
            if r!=rank:continue
            if (r,x,y) in occupied:raise ValueError(f'Overlapping helicopter coordinate: {tree["id"]}/{r}/{x}/{y}')
            occupied.add((r,x,y))
            nodes.append({**node,'id':node['folder'] or node['units'][0],'column':x,'row':y,'left':(x-1)*156+(gap if x>split else 0),'top':top+32+(y-1)*90})
        top+=height
    arrows,internal=research_edges(nodes,tree['edges'])
    return {'mode':'rank_position','width':(columns-1)*156+140+gap,'height':top+12,'divider':split*156-18,'research_columns':split,'nodes':nodes,'ranks':ranks,'arrows':arrows,'internal_edges':internal}
