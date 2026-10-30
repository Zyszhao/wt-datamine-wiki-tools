"""Shared orthogonal research-edge routing, independent of node layout."""
import heapq


def route(start, end, boxes):
    """Find a rectilinear path outside padded cards; retain logical edge identity."""
    xs=sorted({start[0],end[0],*[x for a,b,c,d in boxes for x in (a-8,c+8)]})
    ys=sorted({start[1],end[1],*[y for a,b,c,d in boxes for y in (b-8,d+8)]})
    def clear(p,q):
        x,y=p;xx,yy=q
        return not any((a<x<c and max(min(y,yy),b)<min(max(y,yy),d)) if x==xx
                       else (b<y<d and max(min(x,xx),a)<min(max(x,xx),c)) for a,b,c,d in boxes)
    source=(xs.index(start[0]),ys.index(start[1]),-1)
    queue=[(0,source)];cost={source:0};previous={};last=None
    while queue:
        distance,state=heapq.heappop(queue)
        if distance!=cost[state]:continue
        i,j,direction=state;p=(xs[i],ys[j])
        if p==end:last=state;break
        for ii,jj,axis in ((i-1,j,0),(i+1,j,0),(i,j-1,1),(i,j+1,1)):
            if not (0<=ii<len(xs) and 0<=jj<len(ys)):continue
            q=(xs[ii],ys[jj])
            if not clear(p,q):continue
            next_state=(ii,jj,axis)
            score=distance+abs(p[0]-q[0])+abs(p[1]-q[1])+(18 if direction not in (-1,axis) else 0)
            if score<cost.get(next_state,float('inf')):
                cost[next_state]=score;previous[next_state]=state;heapq.heappush(queue,(score,next_state))
    if last is None:raise ValueError(f'No research path: {start} -> {end}')
    points=[]
    while True:
        points.append([xs[last[0]],ys[last[1]]])
        if last==source:break
        last=previous[last]
    points.reverse();compact=[]
    for p in points:
        if len(compact)>1 and ((compact[-2][0]==compact[-1][0]==p[0]) or (compact[-2][1]==compact[-1][1]==p[1])):compact[-1]=p
        else:compact.append(p)
    return compact


def clear_path(points, boxes):
    for (x,y),(xx,yy) in zip(points,points[1:]):
        if any((a<x<c and max(min(y,yy),b)<min(max(y,yy),d)) if x==xx
               else (b<y<d and max(min(x,xx),a)<min(max(x,xx),c)) for a,b,c,d in boxes):
            return False
    return True


def research_edges(nodes, edges, channel_offset=60, target_gap=8):
    positions={u:n for n in nodes for u in n['units']};arrows=[];internal=[]
    boxes=[(n['left']-4,n['top']-8,n['left']+124,n['top']+52) for n in nodes]
    for edge in edges:
        a=positions[edge['from']];b=positions[edge['to']]
        if a is b:internal.append(edge);continue
        if a['top']==b['top']:
            right=b['left']>a['left']
            start=(a['left']+(130 if right else -10),a['top']+24)
            end=(b['left']+(-10 if right else 130),b['top']+24)
            source_port=[a['left']+(124 if right else -4),a['top']+24]
            target_port=[b['left']+(-4 if right else 124),b['top']+24]
        else:
            start=(a['left']+60,a['top']+60);end=(b['left']+60,b['top']-16)
            source_port=[a['left']+60,a['top']+52]
            target_port=[b['left']+60,b['top']-target_gap]
        # Fix the final approach direction: horizontal into a side, downward
        # into the top. A shortest path alone may finish sideways above a card.
        if a['top']<b['top']:
            # Use the gap immediately BELOW the parent row. Shortest-path
            # routing can otherwise turn after a rank boundary or leave only
            # eight pixels for the final stem, swallowing the arrowhead.
            next_top=min(n['top'] for n in nodes if n['top']>a['top'])
            channel=min(a['top']+channel_offset,(a['top']+48+next_top)/2)
            preferred=[source_port,[source_port[0],channel],[target_port[0],channel],target_port]
            points=preferred if clear_path(preferred,boxes) else [source_port,*route(start,end,boxes),target_port]
        else:
            points=[source_port,*route(start,end,boxes),target_port]
        compact=[]
        for point in points:
            if compact and compact[-1]==point:continue
            if len(compact)>1 and (compact[-2][0]==compact[-1][0]==point[0] or compact[-2][1]==compact[-1][1]==point[1]):compact[-1]=point
            else:compact.append(point)
        points=compact
        arrows.append({**edge,'source':a['id'],'target':b['id'],'c1':a['column'],'c2':b['column'],'x1':start[0],'y1':start[1],'x2':end[0],'y2':end[1],'points':points})
    return arrows,internal
