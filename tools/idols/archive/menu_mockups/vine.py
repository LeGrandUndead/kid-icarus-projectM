# The vine geometry, as the game will draw it (units: window 240 tall).
import math
def catmull(pts, n=12):
    out=[]
    P=[pts[0]]+pts+[pts[-1]]
    for i in range(1,len(P)-2):
        p0,p1,p2,p3=P[i-1],P[i],P[i+1],P[i+2]
        for k in range(n):
            t=k/n; t2=t*t; t3=t2*t
            out.append(tuple(0.5*((2*p1[j])+(-p0[j]+p2[j])*t+(2*p0[j]-5*p1[j]+4*p2[j]-p3[j])*t2+(-p0[j]+3*p1[j]-3*p2[j]+p3[j])*t3) for j in range(2)))
    out.append(pts[-1]); return out
def ribbon(path, w0, w1):
    # polygon of a tapered stroke along path
    L=[0]
    for a,b in zip(path,path[1:]): L.append(L[-1]+math.dist(a,b))
    left=[];right=[]
    for i,p in enumerate(path):
        a=path[max(i-1,0)]; b=path[min(i+1,len(path)-1)]
        dx,dy=b[0]-a[0],b[1]-a[1]; d=math.hypot(dx,dy) or 1
        nx,ny=-dy/d,dx/d; w=(w0+(w1-w0)*L[i]/L[-1])/2
        left.append((p[0]+nx*w,p[1]+ny*w)); right.append((p[0]-nx*w,p[1]-ny*w))
    return left+right[::-1]
def spiral(c, r0, turns, start, sign=1, n=40):
    return [(c[0]+r0*(1-k/n*0.85)*math.cos(start+sign*k/n*turns*2*math.pi), c[1]+r0*(1-k/n*0.85)*math.sin(start+sign*k/n*turns*2*math.pi)) for k in range(n+1)]
def leaf(at, angle, length, width):
    pts=[]
    for k in range(17):
        t=k/16; w=(math.sin(math.pi*t**0.8)**1.2)*width/2
        pts.append((t*length, w))
    pts+= [(x,-y) for x,y in reversed(pts)]
    ca,sa=math.cos(angle),math.sin(angle)
    return [(at[0]+x*ca-y*sa, at[1]+x*sa+y*ca) for x,y in pts]
def vine(buttons):
    """buttons: list of (left, top, right, bottom) in units, current places.
    Returns polygons (black), drawn behind the buttons."""
    polys=[]
    spine=[(-16,-6),(-2,8),(6,14)]
    for i,(l,t,r,b) in enumerate(buttons):
        cy=(t+b)/2; x=l-1+(3 if i%2 else -2)
        spine.append((x,cy))
    lb=buttons[-1]; spine.append((lb[0]+2,lb[3]+10)); spine.append((lb[0]+12,lb[3]+15))
    path=catmull(spine,16)
    polys.append(ribbon(path,9.0,2.6))
    end=path[-1]
    polys.append(ribbon(spiral((end[0]+1,end[1]-6),6,1.25,math.pi/2,-1),2.6,0.8))
    # a flourish where it enters the window
    polys.append(ribbon(spiral((14,6),6.5,1.2,math.pi,1),3.2,0.8))
    # laurel leaves along the spine, in pairs, pointing down the vine
    L=0
    for a,b in zip(path,path[1:]):
        L+=math.dist(a,b)
        if L>11:
            L=0
            ang=math.atan2(b[1]-a[1],b[0]-a[0])
            for side in (1,-1):
                polys.append(leaf(a,ang+side*0.75,9,3.8))
    # a curl hanging between each pair of buttons, on the window side
    for i,((l,t,r,b),(nl,nt,nr,nb)) in enumerate(zip(buttons,buttons[1:])):
        x=min(l,nl)-1; y=(b+nt)/2
        polys.append(ribbon([(x,y)]+spiral((x-4.5,y+0.5),4.2,1.1,0,1),2.4,0.7))
    return polys
