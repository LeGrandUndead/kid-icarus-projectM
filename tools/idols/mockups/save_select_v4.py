exec(open('mk.py').read())
sys_path='/tmp/claude-0/-home-claude/0846ad66-37b8-5f7e-bbd2-eb4c158aa498/scratchpad/render'
import sys; sys.path.insert(0,sys_path)
import books
INK=(16,10,12)
page=paper()
rays(page,960,560,(255,248,228),0.7,spread=1.3)
text(page,(W/2,92),'CHOOSE YOUR BOOK',font(FONT,50),INK+(255,),anchor='mm')
fl,_=art('040','MenTopUp0000'); put(page,fit(mask(fl,INK),w=320),W/2,172,anchor='c')
spots=[(560,1,True,-18),(960,2,False,-6),(1360,3,False,8)]
info=[('Zakuro','32.7%'),('Zakuro','8.1%'),(None,None)]
for x,b,sel,yaw in spots:
    im=books.render(b,480 if sel else 400,yaw,8,4,0)
    im=fit(im,h=440 if sel else 360)
    cy=540-(30 if sel else 0)
    put(page,im,x,cy,anchor='c',sh=(22,0.45,10,30),gl=(15,30,(255,214,96),1.0) if sel else None)
    name,pct=info[b-1]; ty=cy+im.height/2+50
    text(page,(x,cy-im.height/2-44),['I','II','III'][b-1],font(FONT,64 if sel else 52),INK+(255 if sel else 170,),anchor='mm')
    if name:
        text(page,(x,ty),name,font(SANS,46 if sel else 36,900),INK+(255 if sel else 170,),anchor='mm')
        text(page,(x,ty+46),pct,font(SANS,32 if sel else 28,700),INK+(200 if sel else 140,),anchor='mm')
    else: text(page,(x,ty),'New Game',font(SANS,36,900),INK+(170,),anchor='mm')
text(page,(W*0.42,H-70),"Chapter 9: Medusa's Final Battle   ·   04:52:43",font(SANS,32,700),INK+(210,),anchor='mm')
# the menu controls, as on every screen
src=open('menu_anim.py').read(); exec("def controls():"+src.split("def controls():")[1].split("def motes")[0].replace("('▲ ▼','Choose')","('◀ ▶','Choose')"))
page.alpha_composite(controls().transform((W,H),Image.AFFINE,(1,0,0,0,1,0)))
page.convert('RGB').save('mock_save_select_v4.png')
