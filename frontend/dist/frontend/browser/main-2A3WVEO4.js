import{a as mn,b as pn,c as un,e as hn,f as gn,g as fn,h as _n}from"./chunk-WUBCTOIO.js";import{a as Kt}from"./chunk-Y2KXE4O2.js";import{a as kn,b as En}from"./chunk-ITU5IT2I.js";import{a as ln,b as dn}from"./chunk-LJSTTFX2.js";import{a as s}from"./chunk-CUMXHS26.js";import{a as xn,b as Dn}from"./chunk-DSDORQP6.js";import"./chunk-GRI2AAJR.js";import{A as Cn,e as bn,j as ct,k as me,l as mt,n as Ee,q as vn,r as yn,u as wn,x as Mn}from"./chunk-CR2I6BNW.js";import{G as Jt}from"./chunk-SW7XBUG3.js";import{a as Pe}from"./chunk-CS36JUXR.js";import{F as ie,I as ae,L as Zt,M as qt,N as $t,O as cn,P as Ce,Q as xe,a as jt,b as Ht,e as ce,f as dt,h as we,l as Gt,o as Ve,p as Yt,r as Qt,s as je,u as Wt,v as He,y as Xt}from"./chunk-MVNFUC75.js";import{a as I}from"./chunk-UWDMAAJF.js";import{$ as j,$a as It,A as rt,Ac as on,Ba as At,Bc as rn,Cc as sn,Dc as De,Ea as St,Eb as G,Ec as ke,H as B,Ha as O,Hb as Ot,I as q,Ia as P,J as D,Ja as A,Jb as Ft,Ma as Fe,Mb as ye,Na as Be,O as Ie,Oa as U,P as N,Pa as d,Q as L,Qa as c,R as a,Ra as S,Sa as st,Sb as Y,T as y,Ta as Rt,U as w,Ub as F,V as Ct,X as $,Y as z,Ya as R,Z as xt,Za as Tt,_ as V,_a as _,a as Re,aa as Dt,ab as b,ac as Bt,ba as K,bb as E,cb as g,d as x,db as te,ea as le,eb as ve,ec as Nt,fa as k,fb as M,ga as Oe,gb as C,gc as lt,ic as Lt,jc as zt,k as fe,kb as ne,kc as Vt,l as X,lb as Ne,ma as u,mb as f,mc as ze,na as be,nb as Le,nc as Ut,o as _e,oa as kt,ob as p,pb as T,pc as Ue,qa as de,qc as Q,sa as Et,sc as Ge,t as wt,ta as Pt,tc as Ye,u as re,uc as oe,v as Z,va as h,vc as Me,wa as H,wc as en,x as se,xa as J,xc as tn,y as Mt,yc as nn,z as Te,za as ee,zc as an}from"./chunk-ZWUSPUI7.js";import{a as ge,b as Se}from"./chunk-TQPZRHFO.js";var pt=(n,r)=>a(I).isAuthenticated()?!0:a(oe).createUrlTree(["/login"],{queryParams:{returnUrl:r.url}}),Pn=()=>a(I).isAuthenticated()?a(oe).createUrlTree(["/"]):!0,An=()=>a(I).mustChangePassword()?a(oe).createUrlTree(["/change-password"]):!0,m=n=>{let r=n.data.permissions??[],e=n.data.anyPermissions??[],t=a(I);return t.hasAll(r)&&(e.length===0||e.some(o=>t.has(o)))?!0:a(oe).createUrlTree(["/forbidden"])};var Sn="mat-badge-content",Qn=(()=>{class n{static \u0275fac=function(t){return new(t||n)};static \u0275cmp=h({type:n,selectors:[["ng-component"]],decls:0,vars:0,template:function(t,i){},styles:[`.mat-badge {
  position: relative;
}
.mat-badge.mat-badge {
  overflow: visible;
}

.mat-badge-content {
  position: absolute;
  text-align: center;
  display: inline-block;
  transition: transform 200ms ease-in-out;
  transform: scale(0.6);
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  box-sizing: border-box;
  pointer-events: none;
  background-color: var(--mat-badge-background-color, var(--mat-sys-error));
  color: var(--mat-badge-text-color, var(--mat-sys-on-error));
  font-family: var(--mat-badge-text-font, var(--mat-sys-label-small-font));
  font-weight: var(--mat-badge-text-weight, var(--mat-sys-label-small-weight));
  border-radius: var(--mat-badge-container-shape, var(--mat-sys-corner-full));
}
.mat-badge-above .mat-badge-content {
  bottom: 100%;
}
.mat-badge-below .mat-badge-content {
  top: 100%;
}
.mat-badge-before .mat-badge-content {
  right: 100%;
}
[dir=rtl] .mat-badge-before .mat-badge-content {
  right: auto;
  left: 100%;
}
.mat-badge-after .mat-badge-content {
  left: 100%;
}
[dir=rtl] .mat-badge-after .mat-badge-content {
  left: auto;
  right: 100%;
}
@media (forced-colors: active) {
  .mat-badge-content {
    outline: solid 1px;
    border-radius: 0;
  }
}

.mat-badge-disabled .mat-badge-content {
  background-color: var(--mat-badge-disabled-state-background-color, color-mix(in srgb, var(--mat-sys-error) 38%, transparent));
  color: var(--mat-badge-disabled-state-text-color, var(--mat-sys-on-error));
}

.mat-badge-hidden .mat-badge-content {
  display: none;
}

.ng-animate-disabled .mat-badge-content,
.mat-badge-content._mat-animation-noopable {
  transition: none;
}

.mat-badge-content.mat-badge-active {
  transform: none;
}

.mat-badge-small .mat-badge-content {
  width: var(--mat-badge-legacy-small-size-container-size, unset);
  height: var(--mat-badge-legacy-small-size-container-size, unset);
  min-width: var(--mat-badge-small-size-container-size, 6px);
  min-height: var(--mat-badge-small-size-container-size, 6px);
  line-height: var(--mat-badge-small-size-line-height, 6px);
  padding: var(--mat-badge-small-size-container-padding, 0);
  font-size: var(--mat-badge-small-size-text-size, 0);
  margin: var(--mat-badge-small-size-container-offset, -6px 0);
}
.mat-badge-small.mat-badge-overlap .mat-badge-content {
  margin: var(--mat-badge-small-size-container-overlap-offset, -6px);
}

.mat-badge-medium .mat-badge-content {
  width: var(--mat-badge-legacy-container-size, unset);
  height: var(--mat-badge-legacy-container-size, unset);
  min-width: var(--mat-badge-container-size, 16px);
  min-height: var(--mat-badge-container-size, 16px);
  line-height: var(--mat-badge-line-height, 16px);
  padding: var(--mat-badge-container-padding, 0 4px);
  font-size: var(--mat-badge-text-size, var(--mat-sys-label-small-size));
  margin: var(--mat-badge-container-offset, -12px 0);
}
.mat-badge-medium.mat-badge-overlap .mat-badge-content {
  margin: var(--mat-badge-container-overlap-offset, -12px);
}

.mat-badge-large .mat-badge-content {
  width: var(--mat-badge-legacy-large-size-container-size, unset);
  height: var(--mat-badge-legacy-large-size-container-size, unset);
  min-width: var(--mat-badge-large-size-container-size, 16px);
  min-height: var(--mat-badge-large-size-container-size, 16px);
  line-height: var(--mat-badge-large-size-line-height, 16px);
  padding: var(--mat-badge-large-size-container-padding, 0 4px);
  font-size: var(--mat-badge-large-size-text-size, var(--mat-sys-label-small-size));
  margin: var(--mat-badge-large-size-container-offset, -12px 0);
}
.mat-badge-large.mat-badge-overlap .mat-badge-content {
  margin: var(--mat-badge-large-size-container-overlap-offset, -12px);
}
`],encapsulation:2,changeDetection:0})}return n})(),Rn=(()=>{class n{_ngZone=a(j);_elementRef=a(k);_ariaDescriber=a(Xt);_renderer=a(de);_animationsDisabled=ae();_idGenerator=a(He);get color(){return this._color}set color(e){this._setColor(e),this._color=e}_color="primary";overlap=!0;disabled=!1;position="above after";get content(){return this._content}set content(e){this._updateRenderedContent(e)}_content;get description(){return this._description}set description(e){this._updateDescription(e)}_description;size="medium";hidden=!1;_badgeElement;_inlineBadgeDescription;_isInitialized=!1;_interactivityChecker=a(Ve);_document=a(z);constructor(){let e=a(ze);e.load(Qn),e.load(Ut)}isAbove(){return this.position.indexOf("below")===-1}isAfter(){return this.position.indexOf("before")===-1}getBadgeElement(){return this._badgeElement}ngOnInit(){this._clearExistingBadges(),this.content&&!this._badgeElement&&(this._badgeElement=this._createBadgeElement(),this._updateRenderedContent(this.content)),this._isInitialized=!0}ngAfterViewInit(){}ngOnDestroy(){this._renderer.destroyNode&&(this._renderer.destroyNode(this._badgeElement),this._inlineBadgeDescription?.remove()),this._ariaDescriber.removeDescription(this._elementRef.nativeElement,this.description)}_isHostInteractive(){return this._interactivityChecker.isFocusable(this._elementRef.nativeElement,{ignoreVisibility:!0})}_createBadgeElement(){let e=this._renderer.createElement("span"),t="mat-badge-active";return e.setAttribute("id",this._idGenerator.getId("mat-badge-content-")),e.setAttribute("aria-hidden","true"),e.classList.add(Sn),this._animationsDisabled&&e.classList.add("_mat-animation-noopable"),this._elementRef.nativeElement.appendChild(e),typeof requestAnimationFrame=="function"&&!this._animationsDisabled?this._ngZone.runOutsideAngular(()=>{requestAnimationFrame(()=>{e.classList.add(t)})}):e.classList.add(t),e}_updateRenderedContent(e){let t=`${e??""}`.trim();this._isInitialized&&t&&!this._badgeElement&&(this._badgeElement=this._createBadgeElement()),this._badgeElement&&(this._badgeElement.textContent=t),this._content=t}_updateDescription(e){this._ariaDescriber.removeDescription(this._elementRef.nativeElement,this.description),(!e||this._isHostInteractive())&&this._removeInlineDescription(),this._description=e,this._isHostInteractive()?this._ariaDescriber.describe(this._elementRef.nativeElement,e):this._updateInlineDescription()}_updateInlineDescription(){this._inlineBadgeDescription||(this._inlineBadgeDescription=this._document.createElement("span"),this._inlineBadgeDescription.classList.add("cdk-visually-hidden")),this._inlineBadgeDescription.textContent=this.description,this._badgeElement?.appendChild(this._inlineBadgeDescription)}_removeInlineDescription(){this._inlineBadgeDescription?.remove(),this._inlineBadgeDescription=void 0}_setColor(e){let t=this._elementRef.nativeElement.classList;t.remove(`mat-badge-${this._color}`),e&&t.add(`mat-badge-${e}`)}_clearExistingBadges(){let e=this._elementRef.nativeElement.querySelectorAll(`:scope > .${Sn}`);for(let t of Array.from(e))t!==this._badgeElement&&t.remove()}static \u0275fac=function(t){return new(t||n)};static \u0275dir=J({type:n,selectors:[["","matBadge",""]],hostAttrs:[1,"mat-badge"],hostVars:20,hostBindings:function(t,i){t&2&&f("mat-badge-overlap",i.overlap)("mat-badge-above",i.isAbove())("mat-badge-below",!i.isAbove())("mat-badge-before",!i.isAfter())("mat-badge-after",i.isAfter())("mat-badge-small",i.size==="small")("mat-badge-medium",i.size==="medium")("mat-badge-large",i.size==="large")("mat-badge-hidden",i.hidden||!i.content)("mat-badge-disabled",i.disabled)},inputs:{color:[0,"matBadgeColor","color"],overlap:[2,"matBadgeOverlap","overlap",F],disabled:[2,"matBadgeDisabled","disabled",F],position:[0,"matBadgePosition","position"],content:[0,"matBadge","content"],description:[0,"matBadgeDescription","description"],size:[0,"matBadgeSize","size"],hidden:[2,"matBadgeHidden","hidden",F]}})}return n})(),Tn=(()=>{class n{static \u0275fac=function(t){return new(t||n)};static \u0275mod=H({type:n});static \u0275inj=N({imports:[Qt,Q]})}return n})();var Kn=["mat-menu-item",""],Jn=[[["mat-icon"],["","matMenuItemIcon",""]],"*"],ei=["mat-icon, [matMenuItemIcon]","*"];function ti(n,r){n&1&&(Ct(),d(0,"svg",2),S(1,"polygon",3),c())}var ni=["*"];function ii(n,r){if(n&1){let e=R();st(0,"div",0),It("click",function(){y(e);let i=b();return w(i.closed.emit("click"))})("animationstart",function(i){y(e);let o=b();return w(o._onAnimationStart(i.animationName))})("animationend",function(i){y(e);let o=b();return w(o._onAnimationDone(i.animationName))})("animationcancel",function(i){y(e);let o=b();return w(o._onAnimationDone(i.animationName))}),st(1,"div",1),g(2),Rt()()}if(n&2){let e=b();Le(e._classList),f("mat-menu-panel-animations-disabled",e._animationsDisabled)("mat-menu-panel-exit-animation",e._panelAnimationState==="void")("mat-menu-panel-animating",e._isAnimating()),Tt("id",e.panelId),O("aria-label",e.ariaLabel||null)("aria-labelledby",e.ariaLabelledby||null)("aria-describedby",e.ariaDescribedby||null)}}var gt=new L("MAT_MENU_PANEL"),Ae=(()=>{class n{_elementRef=a(k);_document=a(z);_focusMonitor=a(we);_parentMenu=a(gt,{optional:!0});_changeDetectorRef=a(Y);role="menuitem";disabled=!1;disableRipple=!1;_hovered=new x;_focused=new x;_highlighted=!1;_triggersSubmenu=!1;constructor(){a(ze).load(qt),this._parentMenu?.addItem?.(this)}focus(e,t){this._focusMonitor&&e?this._focusMonitor.focusVia(this._getHostElement(),e,t):this._getHostElement().focus(t),this._focused.next(this)}ngAfterViewInit(){this._focusMonitor&&this._focusMonitor.monitor(this._elementRef,!1)}ngOnDestroy(){this._focusMonitor&&this._focusMonitor.stopMonitoring(this._elementRef),this._parentMenu&&this._parentMenu.removeItem&&this._parentMenu.removeItem(this),this._hovered.complete(),this._focused.complete()}_getTabIndex(){return this.disabled?"-1":"0"}_getHostElement(){return this._elementRef.nativeElement}_checkDisabled(e){this.disabled&&(e.preventDefault(),e.stopPropagation())}_handleMouseEnter(){this._hovered.next(this)}getLabel(){let e=this._elementRef.nativeElement.cloneNode(!0),t=e.querySelectorAll("mat-icon, .material-icons");for(let i=0;i<t.length;i++)t[i].remove();return e.textContent?.trim()||""}_setHighlighted(e){this._highlighted=e,this._changeDetectorRef.markForCheck()}_setTriggersSubmenu(e){this._triggersSubmenu=e,this._changeDetectorRef.markForCheck()}_hasFocus(){return this._document&&this._document.activeElement===this._getHostElement()}static \u0275fac=function(t){return new(t||n)};static \u0275cmp=h({type:n,selectors:[["","mat-menu-item",""]],hostAttrs:[1,"mat-mdc-menu-item","mat-focus-indicator"],hostVars:8,hostBindings:function(t,i){t&1&&_("click",function(l){return i._checkDisabled(l)})("mouseenter",function(){return i._handleMouseEnter()}),t&2&&(O("role",i.role)("tabindex",i._getTabIndex())("aria-disabled",i.disabled)("disabled",i.disabled||null),f("mat-mdc-menu-item-highlighted",i._highlighted)("mat-mdc-menu-item-submenu-trigger",i._triggersSubmenu))},inputs:{role:"role",disabled:[2,"disabled","disabled",F],disableRipple:[2,"disableRipple","disableRipple",F]},exportAs:["matMenuItem"],attrs:Kn,ngContentSelectors:ei,decls:5,vars:3,consts:[[1,"mat-mdc-menu-item-text"],["matRipple","",1,"mat-mdc-menu-ripple",3,"matRippleDisabled","matRippleTrigger"],["viewBox","0 0 5 10","focusable","false","aria-hidden","true",1,"mat-mdc-menu-submenu-icon"],["points","0,0 5,5 0,10"]],template:function(t,i){t&1&&(E(Jn),g(0),d(1,"span",0),g(2,1),c(),S(3,"div",1),P(4,ti,2,0,":svg:svg",2)),t&2&&(u(3),U("matRippleDisabled",i.disableRipple||i.disabled)("matRippleTrigger",i._getHostElement()),u(),A(i._triggersSubmenu?4:-1))},dependencies:[Zt],encapsulation:2,changeDetection:0})}return n})();var ai=new L("MatMenuContent");var oi=new L("mat-menu-default-options",{providedIn:"root",factory:()=>({overlapTrigger:!1,xPosition:"after",yPosition:"below",backdropClass:"cdk-overlay-transparent-backdrop"})}),ut="_mat-menu-enter",Qe="_mat-menu-exit",ue=(()=>{class n{_elementRef=a(k);_changeDetectorRef=a(Y);_injector=a($);_keyManager;_xPosition;_yPosition;_firstItemFocusRef;_exitFallbackTimeout;_animationsDisabled=ae();_allItems;_directDescendantItems=new Oe;_classList={};_panelAnimationState="void";_animationDone=new x;_isAnimating=K(!1);parentMenu;direction;overlayPanelClass;backdropClass;ariaLabel;ariaLabelledby;ariaDescribedby;get xPosition(){return this._xPosition}set xPosition(e){this._xPosition=e,this.setPositionClasses()}get yPosition(){return this._yPosition}set yPosition(e){this._yPosition=e,this.setPositionClasses()}templateRef;items;lazyContent;overlapTrigger=!1;hasBackdrop;set panelClass(e){let t=this._previousPanelClass,i=ge({},this._classList);t&&t.length&&t.split(" ").forEach(o=>{i[o]=!1}),this._previousPanelClass=e,e&&e.length&&(e.split(" ").forEach(o=>{i[o]=!0}),this._elementRef.nativeElement.className=""),this._classList=i}_previousPanelClass;get classList(){return this.panelClass}set classList(e){this.panelClass=e}closed=new V;close=this.closed;panelId=a(He).getId("mat-menu-panel-");constructor(){let e=a(oi);this.overlayPanelClass=e.overlayPanelClass||"",this._xPosition=e.xPosition,this._yPosition=e.yPosition,this.backdropClass=e.backdropClass,this.overlapTrigger=e.overlapTrigger,this.hasBackdrop=e.hasBackdrop}ngOnInit(){this.setPositionClasses()}ngAfterContentInit(){this._updateDirectDescendants(),this._keyManager=new Wt(this._directDescendantItems).withWrap().withTypeAhead().withHomeAndEnd(),this._keyManager.tabOut.subscribe(()=>this.closed.emit("tab")),this._directDescendantItems.changes.pipe(B(this._directDescendantItems),q(e=>re(...e.map(t=>t._focused)))).subscribe(e=>this._keyManager.updateActiveItem(e)),this._directDescendantItems.changes.subscribe(e=>{let t=this._keyManager;if(this._panelAnimationState==="enter"&&t.activeItem?._hasFocus()){let i=e.toArray(),o=Math.max(0,Math.min(i.length-1,t.activeItemIndex||0));i[o]&&!i[o].disabled?t.setActiveItem(o):t.setNextItemActive()}})}ngOnDestroy(){this._keyManager?.destroy(),this._directDescendantItems.destroy(),this.closed.complete(),this._firstItemFocusRef?.destroy(),clearTimeout(this._exitFallbackTimeout)}_hovered(){return this._directDescendantItems.changes.pipe(B(this._directDescendantItems),q(t=>re(...t.map(i=>i._hovered))))}addItem(e){}removeItem(e){}_handleKeydown(e){let t=e.keyCode,i=this._keyManager;switch(t){case 27:je(e)||(e.preventDefault(),this.closed.emit("keydown"));break;case 37:this.parentMenu&&this.direction==="ltr"&&this.closed.emit("keydown");break;case 39:this.parentMenu&&this.direction==="rtl"&&this.closed.emit("keydown");break;default:(t===38||t===40)&&i.setFocusOrigin("keyboard"),i.onKeydown(e);return}}focusFirstItem(e="program"){this._firstItemFocusRef?.destroy(),this._firstItemFocusRef=be(()=>{let t=this._resolvePanel();if(!t||!t.contains(document.activeElement)){let i=this._keyManager;i.setFocusOrigin(e).setFirstItemActive(),!i.activeItem&&t&&t.focus()}},{injector:this._injector})}resetActiveItem(){this._keyManager.setActiveItem(-1)}setElevation(e){}setPositionClasses(e=this.xPosition,t=this.yPosition){this._classList=Se(ge({},this._classList),{"mat-menu-before":e==="before","mat-menu-after":e==="after","mat-menu-above":t==="above","mat-menu-below":t==="below"}),this._changeDetectorRef.markForCheck()}_onAnimationDone(e){let t=e===Qe;(t||e===ut)&&(t&&(clearTimeout(this._exitFallbackTimeout),this._exitFallbackTimeout=void 0),this._animationDone.next(t?"void":"enter"),this._isAnimating.set(!1))}_onAnimationStart(e){(e===ut||e===Qe)&&this._isAnimating.set(!0)}_setIsOpen(e){if(this._panelAnimationState=e?"enter":"void",e){if(this._keyManager.activeItemIndex===0){let t=this._resolvePanel();t&&(t.scrollTop=0)}}else this._animationsDisabled||(this._exitFallbackTimeout=setTimeout(()=>this._onAnimationDone(Qe),200));this._animationsDisabled&&setTimeout(()=>{this._onAnimationDone(e?ut:Qe)}),this._changeDetectorRef.markForCheck()}_updateDirectDescendants(){this._allItems.changes.pipe(B(this._allItems)).subscribe(e=>{this._directDescendantItems.reset(e.filter(t=>t._parentMenu===this)),this._directDescendantItems.notifyOnChanges()})}_resolvePanel(){let e=null;return this._directDescendantItems.length&&(e=this._directDescendantItems.first._getHostElement().closest('[role="menu"]')),e}static \u0275fac=function(t){return new(t||n)};static \u0275cmp=h({type:n,selectors:[["mat-menu"]],contentQueries:function(t,i,o){if(t&1&&te(o,ai,5)(o,Ae,5)(o,Ae,4),t&2){let l;M(l=C())&&(i.lazyContent=l.first),M(l=C())&&(i._allItems=l),M(l=C())&&(i.items=l)}},viewQuery:function(t,i){if(t&1&&ve(kt,5),t&2){let o;M(o=C())&&(i.templateRef=o.first)}},hostVars:3,hostBindings:function(t,i){t&2&&O("aria-label",null)("aria-labelledby",null)("aria-describedby",null)},inputs:{backdropClass:"backdropClass",ariaLabel:[0,"aria-label","ariaLabel"],ariaLabelledby:[0,"aria-labelledby","ariaLabelledby"],ariaDescribedby:[0,"aria-describedby","ariaDescribedby"],xPosition:"xPosition",yPosition:"yPosition",overlapTrigger:[2,"overlapTrigger","overlapTrigger",F],hasBackdrop:[2,"hasBackdrop","hasBackdrop",e=>e==null?null:F(e)],panelClass:[0,"class","panelClass"],classList:"classList"},outputs:{closed:"closed",close:"close"},exportAs:["matMenu"],features:[G([{provide:gt,useExisting:n}])],ngContentSelectors:ni,decls:1,vars:0,consts:[["tabindex","-1","role","menu",1,"mat-mdc-menu-panel",3,"click","animationstart","animationend","animationcancel","id"],[1,"mat-mdc-menu-content"]],template:function(t,i){t&1&&(E(),At(0,ii,3,12,"ng-template"))},styles:[`mat-menu {
  display: none;
}

.mat-mdc-menu-content {
  margin: 0;
  padding: 8px 0;
  outline: 0;
}
.mat-mdc-menu-content,
.mat-mdc-menu-content .mat-mdc-menu-item .mat-mdc-menu-item-text {
  -moz-osx-font-smoothing: grayscale;
  -webkit-font-smoothing: antialiased;
  flex: 1;
  white-space: normal;
  font-family: var(--mat-menu-item-label-text-font, var(--mat-sys-label-large-font));
  line-height: var(--mat-menu-item-label-text-line-height, var(--mat-sys-label-large-line-height));
  font-size: var(--mat-menu-item-label-text-size, var(--mat-sys-label-large-size));
  letter-spacing: var(--mat-menu-item-label-text-tracking, var(--mat-sys-label-large-tracking));
  font-weight: var(--mat-menu-item-label-text-weight, var(--mat-sys-label-large-weight));
}

@keyframes _mat-menu-enter {
  from {
    opacity: 0;
    transform: scale(0.8);
  }
  to {
    opacity: 1;
    transform: none;
  }
}
@keyframes _mat-menu-exit {
  from {
    opacity: 1;
  }
  to {
    opacity: 0;
  }
}
.mat-mdc-menu-panel {
  min-width: 112px;
  max-width: 280px;
  overflow: auto;
  box-sizing: border-box;
  outline: 0;
  animation: _mat-menu-enter 120ms cubic-bezier(0, 0, 0.2, 1);
  border-radius: var(--mat-menu-container-shape, var(--mat-sys-corner-extra-small));
  background-color: var(--mat-menu-container-color, var(--mat-sys-surface-container));
  box-shadow: var(--mat-menu-container-elevation-shadow, 0px 3px 1px -2px rgba(0, 0, 0, 0.2), 0px 2px 2px 0px rgba(0, 0, 0, 0.14), 0px 1px 5px 0px rgba(0, 0, 0, 0.12));
  will-change: transform, opacity;
}
.mat-mdc-menu-panel.mat-menu-panel-exit-animation {
  animation: _mat-menu-exit 100ms 25ms linear forwards;
}
.mat-mdc-menu-panel.mat-menu-panel-animations-disabled {
  animation: none;
}
.mat-mdc-menu-panel.mat-menu-panel-animating {
  pointer-events: none;
}
.mat-mdc-menu-panel.mat-menu-panel-animating:has(.mat-mdc-menu-content:empty) {
  display: none;
}
@media (forced-colors: active) {
  .mat-mdc-menu-panel {
    outline: solid 1px;
  }
}
.mat-mdc-menu-panel .mat-divider {
  border-top-color: var(--mat-menu-divider-color, var(--mat-sys-surface-variant));
  margin-bottom: var(--mat-menu-divider-bottom-spacing, 8px);
  margin-top: var(--mat-menu-divider-top-spacing, 8px);
}

.mat-mdc-menu-item {
  display: flex;
  position: relative;
  align-items: center;
  justify-content: flex-start;
  overflow: hidden;
  padding: 0;
  cursor: pointer;
  width: 100%;
  text-align: left;
  box-sizing: border-box;
  color: inherit;
  font-size: inherit;
  background: none;
  text-decoration: none;
  margin: 0;
  min-height: 48px;
  padding-left: var(--mat-menu-item-leading-spacing, 12px);
  padding-right: var(--mat-menu-item-trailing-spacing, 12px);
  -webkit-user-select: none;
  user-select: none;
  cursor: pointer;
  outline: none;
  border: none;
  -webkit-tap-highlight-color: transparent;
}
.mat-mdc-menu-item::-moz-focus-inner {
  border: 0;
}
[dir=rtl] .mat-mdc-menu-item {
  padding-left: var(--mat-menu-item-trailing-spacing, 12px);
  padding-right: var(--mat-menu-item-leading-spacing, 12px);
}
.mat-mdc-menu-item:has(.material-icons, mat-icon, [matButtonIcon]) {
  padding-left: var(--mat-menu-item-with-icon-leading-spacing, 12px);
  padding-right: var(--mat-menu-item-with-icon-trailing-spacing, 12px);
}
[dir=rtl] .mat-mdc-menu-item:has(.material-icons, mat-icon, [matButtonIcon]) {
  padding-left: var(--mat-menu-item-with-icon-trailing-spacing, 12px);
  padding-right: var(--mat-menu-item-with-icon-leading-spacing, 12px);
}
.mat-mdc-menu-item, .mat-mdc-menu-item:visited, .mat-mdc-menu-item:link {
  color: var(--mat-menu-item-label-text-color, var(--mat-sys-on-surface));
}
.mat-mdc-menu-item .mat-icon-no-color,
.mat-mdc-menu-item .mat-mdc-menu-submenu-icon {
  color: var(--mat-menu-item-icon-color, var(--mat-sys-on-surface-variant));
}
.mat-mdc-menu-item[disabled] {
  cursor: default;
  opacity: 0.38;
}
.mat-mdc-menu-item[disabled]::after {
  display: block;
  position: absolute;
  content: "";
  top: 0;
  left: 0;
  bottom: 0;
  right: 0;
}
.mat-mdc-menu-item:focus {
  outline: 0;
}
.mat-mdc-menu-item .mat-icon {
  flex-shrink: 0;
  margin-right: var(--mat-menu-item-spacing, 12px);
  height: var(--mat-menu-item-icon-size, 24px);
  width: var(--mat-menu-item-icon-size, 24px);
}
[dir=rtl] .mat-mdc-menu-item {
  text-align: right;
}
[dir=rtl] .mat-mdc-menu-item .mat-icon {
  margin-right: 0;
  margin-left: var(--mat-menu-item-spacing, 12px);
}
.mat-mdc-menu-item:not([disabled]):hover {
  background-color: var(--mat-menu-item-hover-state-layer-color, color-mix(in srgb, var(--mat-sys-on-surface) calc(var(--mat-sys-hover-state-layer-opacity) * 100%), transparent));
}
.mat-mdc-menu-item:not([disabled]).cdk-program-focused, .mat-mdc-menu-item:not([disabled]).cdk-keyboard-focused, .mat-mdc-menu-item:not([disabled]).mat-mdc-menu-item-highlighted {
  background-color: var(--mat-menu-item-focus-state-layer-color, color-mix(in srgb, var(--mat-sys-on-surface) calc(var(--mat-sys-focus-state-layer-opacity) * 100%), transparent));
}
@media (forced-colors: active) {
  .mat-mdc-menu-item {
    margin-top: 1px;
  }
}

.mat-mdc-menu-submenu-icon {
  width: var(--mat-menu-item-icon-size, 24px);
  height: 10px;
  fill: currentColor;
  padding-left: var(--mat-menu-item-spacing, 12px);
}
[dir=rtl] .mat-mdc-menu-submenu-icon {
  padding-right: var(--mat-menu-item-spacing, 12px);
  padding-left: 0;
}
[dir=rtl] .mat-mdc-menu-submenu-icon polygon {
  transform: scaleX(-1);
  transform-origin: center;
}
@media (forced-colors: active) {
  .mat-mdc-menu-submenu-icon {
    fill: CanvasText;
  }
}

.mat-mdc-menu-item .mat-mdc-menu-ripple {
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  position: absolute;
  pointer-events: none;
}
`],encapsulation:2,changeDetection:0})}return n})(),ri=new L("mat-menu-scroll-strategy",{providedIn:"root",factory:()=>{let n=a($);return()=>vn(n)}});var pe=new WeakMap,si=(()=>{class n{_canHaveBackdrop;_element=a(k);_viewContainerRef=a(Pt);_menuItemInstance=a(Ae,{optional:!0,self:!0});_dir=a(Ue,{optional:!0});_focusMonitor=a(we);_ngZone=a(j);_injector=a($);_scrollStrategy=a(ri);_changeDetectorRef=a(Y);_animationsDisabled=ae();_portal;_overlayRef=null;_menuOpen=!1;_closingActionsSubscription=Re.EMPTY;_menuCloseSubscription=Re.EMPTY;_pendingRemoval;_parentMaterialMenu;_parentInnerPadding;_openedBy=void 0;get _menu(){return this._menuInternal}set _menu(e){e!==this._menuInternal&&(this._menuInternal=e,this._menuCloseSubscription.unsubscribe(),e&&(this._parentMaterialMenu,this._menuCloseSubscription=e.close.subscribe(t=>{this._destroyMenu(t),(t==="click"||t==="tab")&&this._parentMaterialMenu&&this._parentMaterialMenu.closed.emit(t)})),this._menuItemInstance?._setTriggersSubmenu(this._triggersSubmenu()))}_menuInternal=null;constructor(e){this._canHaveBackdrop=e;let t=a(gt,{optional:!0});this._parentMaterialMenu=t instanceof ue?t:void 0}ngOnDestroy(){this._menu&&this._ownsMenu(this._menu)&&pe.delete(this._menu),this._pendingRemoval?.unsubscribe(),this._menuCloseSubscription.unsubscribe(),this._closingActionsSubscription.unsubscribe(),this._overlayRef&&(this._overlayRef.dispose(),this._overlayRef=null)}get menuOpen(){return this._menuOpen}get dir(){return this._dir&&this._dir.value==="rtl"?"rtl":"ltr"}_triggersSubmenu(){return!!(this._menuItemInstance&&this._parentMaterialMenu&&this._menu)}_closeMenu(){this._menu?.close.emit()}_openMenu(e){if(this._triggerIsAriaDisabled())return;let t=this._menu;if(this._menuOpen||!t)return;this._pendingRemoval?.unsubscribe();let i=pe.get(t);pe.set(t,this),i&&i!==this&&i._closeMenu();let o=this._createOverlay(t),l=o.getConfig(),v=l.positionStrategy;this._setPosition(t,v),this._canHaveBackdrop?l.hasBackdrop=t.hasBackdrop==null?!this._triggersSubmenu():t.hasBackdrop:l.hasBackdrop=t.hasBackdrop??!1,o.hasAttached()||(o.attach(this._getPortal(t)),t.lazyContent?.attach(this.menuData)),this._closingActionsSubscription=this._menuClosingActions().subscribe(()=>this._closeMenu()),t.parentMenu=this._triggersSubmenu()?this._parentMaterialMenu:void 0,t.direction=this.dir,e&&t.focusFirstItem(this._openedBy||"program"),this._setIsMenuOpen(!0),t instanceof ue&&(t._setIsOpen(!0),t._directDescendantItems.changes.pipe(D(t.close)).subscribe(()=>{v.withLockedPosition(!1).reapplyLastPosition(),v.withLockedPosition(!0)}))}focus(e,t){this._focusMonitor&&e?this._focusMonitor.focusVia(this._element,e,t):this._element.nativeElement.focus(t)}_destroyMenu(e){let t=this._overlayRef,i=this._menu;!t||!this.menuOpen||(this._closingActionsSubscription.unsubscribe(),this._pendingRemoval?.unsubscribe(),i instanceof ue&&this._ownsMenu(i)?(this._pendingRemoval=i._animationDone.pipe(Te(1)).subscribe(()=>{t.detach(),pe.has(i)||i.lazyContent?.detach()}),i._setIsOpen(!1)):(t.detach(),i?.lazyContent?.detach()),i&&this._ownsMenu(i)&&pe.delete(i),this.restoreFocus&&(e==="keydown"||!this._openedBy||!this._triggersSubmenu())&&this.focus(this._openedBy),this._openedBy=void 0,this._setIsMenuOpen(!1))}_setIsMenuOpen(e){e!==this._menuOpen&&(this._menuOpen=e,this._menuOpen?this.menuOpened.emit():this.menuClosed.emit(),this._triggersSubmenu()&&this._menuItemInstance._setHighlighted(e),this._changeDetectorRef.markForCheck())}_createOverlay(e){if(!this._overlayRef){let t=this._getOverlayConfig(e);this._subscribeToPositions(e,t.positionStrategy),this._overlayRef=Mn(this._injector,t),this._overlayRef.keydownEvents().subscribe(i=>{this._menu instanceof ue&&this._menu._handleKeydown(i)})}return this._overlayRef}_getOverlayConfig(e){return new yn({positionStrategy:wn(this._injector,this._getOverlayOrigin()).withLockedPosition().withGrowAfterOpen().withTransformOriginOn(".mat-menu-panel, .mat-mdc-menu-panel"),backdropClass:e.backdropClass||"cdk-overlay-transparent-backdrop",panelClass:e.overlayPanelClass,scrollStrategy:this._scrollStrategy(),direction:this._dir||"ltr",disableAnimations:this._animationsDisabled})}_subscribeToPositions(e,t){e.setPositionClasses&&t.positionChanges.subscribe(i=>{this._ngZone.run(()=>{let o=i.connectionPair.overlayX==="start"?"after":"before",l=i.connectionPair.overlayY==="top"?"below":"above";e.setPositionClasses(o,l)})})}_setPosition(e,t){let[i,o]=e.xPosition==="before"?["end","start"]:["start","end"],[l,v]=e.yPosition==="above"?["bottom","top"]:["top","bottom"],[nt,it]=[l,v],[at,ot]=[i,o],he=0;if(this._triggersSubmenu()){if(ot=i=e.xPosition==="before"?"start":"end",o=at=i==="end"?"start":"end",this._parentMaterialMenu){if(this._parentInnerPadding==null){let yt=this._parentMaterialMenu.items.first;this._parentInnerPadding=yt?yt._getHostElement().offsetTop:0}he=l==="bottom"?this._parentInnerPadding:-this._parentInnerPadding}}else e.overlapTrigger||(nt=l==="top"?"bottom":"top",it=v==="top"?"bottom":"top");t.withPositions([{originX:i,originY:nt,overlayX:at,overlayY:l,offsetY:he},{originX:o,originY:nt,overlayX:ot,overlayY:l,offsetY:he},{originX:i,originY:it,overlayX:at,overlayY:v,offsetY:-he},{originX:o,originY:it,overlayX:ot,overlayY:v,offsetY:-he}])}_menuClosingActions(){let e=this._getOutsideClickStream(this._overlayRef),t=this._overlayRef.detachments(),i=this._parentMaterialMenu?this._parentMaterialMenu.closed:fe(),o=this._parentMaterialMenu?this._parentMaterialMenu._hovered().pipe(Z(l=>this._menuOpen&&l!==this._menuItemInstance)):fe();return re(e,i,o,t)}_getPortal(e){return(!this._portal||this._portal.templateRef!==e.templateRef)&&(this._portal=new bn(e.templateRef,this._viewContainerRef)),this._portal}_ownsMenu(e){return pe.get(e)===this}_triggerIsAriaDisabled(){return F(this._element.nativeElement.getAttribute("aria-disabled"))}static \u0275fac=function(t){Et()};static \u0275dir=J({type:n})}return n})(),Fn=(()=>{class n extends si{_cleanupTouchstart;_hoverSubscription=Re.EMPTY;get _deprecatedMatMenuTriggerFor(){return this.menu}set _deprecatedMatMenuTriggerFor(e){this.menu=e}get menu(){return this._menu}set menu(e){this._menu=e}menuData;restoreFocus=!0;menuOpened=new V;onMenuOpen=this.menuOpened;menuClosed=new V;onMenuClose=this.menuClosed;constructor(){super(!0);let e=a(de);this._cleanupTouchstart=e.listen(this._element.nativeElement,"touchstart",t=>{Ht(t)||(this._openedBy="touch")},{passive:!0})}triggersSubmenu(){return super._triggersSubmenu()}toggleMenu(){return this.menuOpen?this.closeMenu():this.openMenu()}openMenu(){this._openMenu(!0)}closeMenu(){this._closeMenu()}updatePosition(){this._overlayRef?.updatePosition()}ngAfterContentInit(){this._handleHover()}ngOnDestroy(){super.ngOnDestroy(),this._cleanupTouchstart(),this._hoverSubscription.unsubscribe()}_getOverlayOrigin(){return this._element}_getOutsideClickStream(e){return e.backdropClick()}_handleMousedown(e){jt(e)||(this._openedBy=e.button===0?"mouse":void 0,this.triggersSubmenu()&&e.preventDefault())}_handleKeydown(e){let t=e.keyCode;(t===13||t===32)&&(this._openedBy="keyboard"),this.triggersSubmenu()&&(t===39&&this.dir==="ltr"||t===37&&this.dir==="rtl")&&(this._openedBy="keyboard",this.openMenu())}_handleClick(e){this.triggersSubmenu()?(e.stopPropagation(),this.openMenu()):this.toggleMenu()}_handleHover(){this.triggersSubmenu()&&this._parentMaterialMenu&&(this._hoverSubscription=this._parentMaterialMenu._hovered().subscribe(e=>{e===this._menuItemInstance&&!e.disabled&&this._parentMaterialMenu?._panelAnimationState!=="void"&&(this._openedBy="mouse",this._openMenu(!1))}))}static \u0275fac=function(t){return new(t||n)};static \u0275dir=J({type:n,selectors:[["","mat-menu-trigger-for",""],["","matMenuTriggerFor",""]],hostAttrs:[1,"mat-mdc-menu-trigger"],hostVars:3,hostBindings:function(t,i){t&1&&_("click",function(l){return i._handleClick(l)})("mousedown",function(l){return i._handleMousedown(l)})("keydown",function(l){return i._handleKeydown(l)}),t&2&&O("aria-haspopup",i.menu?"menu":null)("aria-expanded",i.menuOpen)("aria-controls",i.menuOpen?i.menu==null?null:i.menu.panelId:null)},inputs:{_deprecatedMatMenuTriggerFor:[0,"mat-menu-trigger-for","_deprecatedMatMenuTriggerFor"],menu:[0,"matMenuTriggerFor","menu"],menuData:[0,"matMenuTriggerData","menuData"],restoreFocus:[0,"matMenuTriggerRestoreFocus","restoreFocus"]},outputs:{menuOpened:"menuOpened",onMenuOpen:"onMenuOpen",menuClosed:"menuClosed",onMenuClose:"onMenuClose"},exportAs:["matMenuTrigger"],features:[ee]})}return n})();var Bn=(()=>{class n{static \u0275fac=function(t){return new(t||n)};static \u0275mod=H({type:n});static \u0275inj=N({imports:[$t,Cn,Q,Ee]})}return n})();var Ze=["*"],di=["content"],ci=[[["mat-drawer"]],[["mat-drawer-content"]],"*"],mi=["mat-drawer","mat-drawer-content","*"];function pi(n,r){if(n&1){let e=R();d(0,"div",1),_("click",function(){y(e);let i=b();return w(i._onBackdropClicked())}),c()}if(n&2){let e=b();f("mat-drawer-shown",e._isShowingBackdrop())}}function ui(n,r){n&1&&(d(0,"mat-drawer-content"),g(1,2),c())}var hi=[[["mat-sidenav"]],[["mat-sidenav-content"]],"*"],gi=["mat-sidenav","mat-sidenav-content","*"];function fi(n,r){if(n&1){let e=R();d(0,"div",1),_("click",function(){y(e);let i=b();return w(i._onBackdropClicked())}),c()}if(n&2){let e=b();f("mat-drawer-shown",e._isShowingBackdrop())}}function _i(n,r){n&1&&(d(0,"mat-sidenav-content"),g(1,2),c())}var bi=`.mat-drawer-container {
  position: relative;
  z-index: 1;
  color: var(--mat-sidenav-content-text-color, var(--mat-sys-on-background));
  background-color: var(--mat-sidenav-content-background-color, var(--mat-sys-background));
  box-sizing: border-box;
  display: block;
  overflow: hidden;
}
.mat-drawer-container[fullscreen] {
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  position: absolute;
}
.mat-drawer-container[fullscreen].mat-drawer-container-has-open {
  overflow: hidden;
}
.mat-drawer-container.mat-drawer-container-explicit-backdrop .mat-drawer-side {
  z-index: 3;
}
.mat-drawer-container.ng-animate-disabled .mat-drawer-backdrop,
.mat-drawer-container.ng-animate-disabled .mat-drawer-content, .ng-animate-disabled .mat-drawer-container .mat-drawer-backdrop,
.ng-animate-disabled .mat-drawer-container .mat-drawer-content {
  transition: none;
}

.mat-drawer-backdrop {
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  position: absolute;
  display: block;
  z-index: 3;
  visibility: hidden;
}
.mat-drawer-backdrop.mat-drawer-shown {
  visibility: visible;
  background-color: var(--mat-sidenav-scrim-color, color-mix(in srgb, var(--mat-sys-neutral-variant20) 40%, transparent));
}
.mat-drawer-transition .mat-drawer-backdrop {
  transition-duration: 400ms;
  transition-timing-function: cubic-bezier(0.25, 0.8, 0.25, 1);
  transition-property: background-color, visibility;
}
@media (forced-colors: active) {
  .mat-drawer-backdrop {
    opacity: 0.5;
  }
}

.mat-drawer-content {
  position: relative;
  z-index: 1;
  display: block;
  height: 100%;
  overflow: auto;
}
.mat-drawer-content.mat-drawer-content-hidden {
  opacity: 0;
}
.mat-drawer-transition .mat-drawer-content {
  transition-duration: 400ms;
  transition-timing-function: cubic-bezier(0.25, 0.8, 0.25, 1);
  transition-property: transform, margin-left, margin-right;
}

.mat-drawer {
  position: relative;
  z-index: 4;
  color: var(--mat-sidenav-container-text-color, var(--mat-sys-on-surface-variant));
  box-shadow: var(--mat-sidenav-container-elevation-shadow, none);
  background-color: var(--mat-sidenav-container-background-color, var(--mat-sys-surface));
  border-top-right-radius: var(--mat-sidenav-container-shape, var(--mat-sys-corner-large));
  border-bottom-right-radius: var(--mat-sidenav-container-shape, var(--mat-sys-corner-large));
  width: var(--mat-sidenav-container-width, 360px);
  display: block;
  position: absolute;
  top: 0;
  bottom: 0;
  z-index: 3;
  outline: 0;
  box-sizing: border-box;
  overflow-y: auto;
  transform: translate3d(-100%, 0, 0);
}
@media (forced-colors: active) {
  .mat-drawer, [dir=rtl] .mat-drawer.mat-drawer-end {
    border-right: solid 1px currentColor;
  }
}
@media (forced-colors: active) {
  [dir=rtl] .mat-drawer, .mat-drawer.mat-drawer-end {
    border-left: solid 1px currentColor;
    border-right: none;
  }
}
.mat-drawer.mat-drawer-side {
  z-index: 2;
}
.mat-drawer.mat-drawer-end {
  right: 0;
  transform: translate3d(100%, 0, 0);
  border-top-left-radius: var(--mat-sidenav-container-shape, var(--mat-sys-corner-large));
  border-bottom-left-radius: var(--mat-sidenav-container-shape, var(--mat-sys-corner-large));
  border-top-right-radius: 0;
  border-bottom-right-radius: 0;
}
[dir=rtl] .mat-drawer {
  border-top-left-radius: var(--mat-sidenav-container-shape, var(--mat-sys-corner-large));
  border-bottom-left-radius: var(--mat-sidenav-container-shape, var(--mat-sys-corner-large));
  border-top-right-radius: 0;
  border-bottom-right-radius: 0;
  transform: translate3d(100%, 0, 0);
}
[dir=rtl] .mat-drawer.mat-drawer-end {
  border-top-right-radius: var(--mat-sidenav-container-shape, var(--mat-sys-corner-large));
  border-bottom-right-radius: var(--mat-sidenav-container-shape, var(--mat-sys-corner-large));
  border-top-left-radius: 0;
  border-bottom-left-radius: 0;
  left: 0;
  right: auto;
  transform: translate3d(-100%, 0, 0);
}
.mat-drawer-transition .mat-drawer {
  transition: transform 400ms cubic-bezier(0.25, 0.8, 0.25, 1);
}
.mat-drawer:not(.mat-drawer-opened):not(.mat-drawer-animating) {
  visibility: hidden;
  box-shadow: none;
}
.mat-drawer:not(.mat-drawer-opened):not(.mat-drawer-animating) .mat-drawer-inner-container {
  display: none;
}
.mat-drawer.mat-drawer-opened.mat-drawer-opened {
  transform: none;
}

.mat-drawer-side {
  box-shadow: none;
  border-right-color: var(--mat-sidenav-container-divider-color, transparent);
  border-right-width: 1px;
  border-right-style: solid;
}
.mat-drawer-side.mat-drawer-end {
  border-left-color: var(--mat-sidenav-container-divider-color, transparent);
  border-left-width: 1px;
  border-left-style: solid;
  border-right: none;
}
[dir=rtl] .mat-drawer-side {
  border-left-color: var(--mat-sidenav-container-divider-color, transparent);
  border-left-width: 1px;
  border-left-style: solid;
  border-right: none;
}
[dir=rtl] .mat-drawer-side.mat-drawer-end {
  border-right-color: var(--mat-sidenav-container-divider-color, transparent);
  border-right-width: 1px;
  border-right-style: solid;
  border-left: none;
}

.mat-drawer-inner-container {
  width: 100%;
  height: 100%;
  overflow: auto;
}

.mat-sidenav-fixed {
  position: fixed;
}
`;var vi=new L("MAT_DRAWER_DEFAULT_AUTOSIZE",{providedIn:"root",factory:()=>!1}),bt=new L("MAT_DRAWER_CONTAINER"),We=(()=>{class n extends me{_platform=a(ce);_changeDetectorRef=a(Y);_container=a(_t);constructor(){let e=a(k),t=a(ct),i=a(j);super(e,t,i)}ngAfterContentInit(){this._container._contentMarginChanges.subscribe(()=>{this._changeDetectorRef.markForCheck()})}_shouldBeHidden(){if(this._platform.isBrowser)return!1;let{start:e,end:t}=this._container;return e!=null&&e.mode!=="over"&&e.opened||t!=null&&t.mode!=="over"&&t.opened}static \u0275fac=function(t){return new(t||n)};static \u0275cmp=h({type:n,selectors:[["mat-drawer-content"]],hostAttrs:[1,"mat-drawer-content"],hostVars:6,hostBindings:function(t,i){t&2&&(Ne("margin-left",i._container._contentMargins.left,"px")("margin-right",i._container._contentMargins.right,"px"),f("mat-drawer-content-hidden",i._shouldBeHidden()))},features:[G([{provide:me,useExisting:n}]),ee],ngContentSelectors:Ze,decls:1,vars:0,template:function(t,i){t&1&&(E(),g(0))},encapsulation:2,changeDetection:0})}return n})(),ft=(()=>{class n{_elementRef=a(k);_focusTrapFactory=a(Yt);_focusMonitor=a(we);_platform=a(ce);_ngZone=a(j);_renderer=a(de);_interactivityChecker=a(Ve);_doc=a(z);_container=a(bt,{optional:!0});_focusTrap=null;_elementFocusedBeforeDrawerWasOpened=null;_eventCleanups;_isAttached=!1;_anchor=null;get position(){return this._position}set position(e){e=e==="end"?"end":"start",e!==this._position&&(this._isAttached&&this._updatePositionInParent(e),this._position=e,this.onPositionChanged.emit())}_position="start";get mode(){return this._mode}set mode(e){this._mode=e,this._updateFocusTrapState(),this._modeChanged.next()}_mode="over";get disableClose(){return this._disableClose}set disableClose(e){this._disableClose=ie(e)}_disableClose=!1;get autoFocus(){let e=this._autoFocus;return e??(this.mode==="side"?"dialog":"first-tabbable")}set autoFocus(e){(e==="true"||e==="false"||e==null)&&(e=ie(e)),this._autoFocus=e}_autoFocus;get opened(){return this._opened()}set opened(e){this.toggle(ie(e))}_opened=K(!1);_openedVia=null;_animationStarted=new x;_animationEnd=new x;openedChange=new V(!0);_openedStream=this.openedChange.pipe(Z(e=>e),_e(()=>{}));openedStart=this._animationStarted.pipe(Z(()=>this.opened),rt(void 0));_closedStream=this.openedChange.pipe(Z(e=>!e),_e(()=>{}));closedStart=this._animationStarted.pipe(Z(()=>!this.opened),rt(void 0));_destroyed=new x;onPositionChanged=new V;_content;_modeChanged=new x;_injector=a($);_changeDetectorRef=a(Y);constructor(){this.openedChange.pipe(D(this._destroyed)).subscribe(e=>{e?(this._elementFocusedBeforeDrawerWasOpened=this._doc.activeElement,this._takeFocus()):this._isFocusWithinDrawer()&&this._restoreFocus(this._openedVia||"program")}),this._eventCleanups=this._ngZone.runOutsideAngular(()=>{let e=this._renderer,t=this._elementRef.nativeElement;return[e.listen(t,"keydown",i=>{i.keyCode===27&&!this.disableClose&&!je(i)&&this._ngZone.run(()=>{this.close(),i.stopPropagation(),i.preventDefault()})}),e.listen(t,"transitionend",this._handleTransitionEvent),e.listen(t,"transitioncancel",this._handleTransitionEvent)]}),this._animationEnd.subscribe(()=>{this.openedChange.emit(this.opened)})}_forceFocus(e,t){this._interactivityChecker.isFocusable(e)||(e.tabIndex=-1,this._ngZone.runOutsideAngular(()=>{let i=()=>{o(),l(),e.removeAttribute("tabindex")},o=this._renderer.listen(e,"blur",i),l=this._renderer.listen(e,"mousedown",i)})),e.focus(t)}_focusByCssSelector(e,t){let i=this._elementRef.nativeElement.querySelector(e);i&&this._forceFocus(i,t)}_takeFocus(){if(!this._focusTrap)return;let e=this._elementRef.nativeElement;switch(this.autoFocus){case!1:case"dialog":return;case!0:case"first-tabbable":be(()=>{!this._focusTrap.focusInitialElement()&&typeof e.focus=="function"&&e.focus()},{injector:this._injector});break;case"first-heading":this._focusByCssSelector('h1, h2, h3, h4, h5, h6, [role="heading"]');break;default:this._focusByCssSelector(this.autoFocus);break}}_restoreFocus(e){this.autoFocus!=="dialog"&&(this._elementFocusedBeforeDrawerWasOpened?this._focusMonitor.focusVia(this._elementFocusedBeforeDrawerWasOpened,e):this._elementRef.nativeElement.blur(),this._elementFocusedBeforeDrawerWasOpened=null)}_isFocusWithinDrawer(){let e=this._doc.activeElement;return!!e&&this._elementRef.nativeElement.contains(e)}ngAfterViewInit(){this._isAttached=!0,this._position==="end"&&this._updatePositionInParent("end"),this._platform.isBrowser&&(this._focusTrap=this._focusTrapFactory.create(this._elementRef.nativeElement),this._updateFocusTrapState())}ngOnDestroy(){this._eventCleanups.forEach(e=>e()),this._focusTrap?.destroy(),this._anchor?.remove(),this._anchor=null,this._animationStarted.complete(),this._animationEnd.complete(),this._modeChanged.complete(),this._destroyed.next(),this._destroyed.complete()}open(e){return this.toggle(!0,e)}close(){return this.toggle(!1)}_closeViaBackdropClick(){return this._setOpen(!1,!0,"mouse")}toggle(e=!this.opened,t){e&&t&&(this._openedVia=t);let i=this._setOpen(e,!e&&this._isFocusWithinDrawer(),this._openedVia||"program");return e||(this._openedVia=null),i}_setOpen(e,t,i){return e===this.opened?Promise.resolve(e?"open":"close"):(this._opened.set(e),this._container?._transitionsEnabled?(this._setIsAnimating(!0),setTimeout(()=>this._animationStarted.next())):setTimeout(()=>{this._animationStarted.next(),this._animationEnd.next()}),this._elementRef.nativeElement.classList.toggle("mat-drawer-opened",e),!e&&t&&this._restoreFocus(i),this._changeDetectorRef.markForCheck(),this._updateFocusTrapState(),new Promise(o=>{this.openedChange.pipe(Te(1)).subscribe(l=>o(l?"open":"close"))}))}_setIsAnimating(e){this._elementRef.nativeElement.classList.toggle("mat-drawer-animating",e)}_getWidth(){return this._elementRef.nativeElement.offsetWidth||0}_updateFocusTrapState(){this._focusTrap&&(this._focusTrap.enabled=this.opened&&!!this._container?._isShowingBackdrop())}_updatePositionInParent(e){if(!this._platform.isBrowser)return;let t=this._elementRef.nativeElement,i=t.parentNode;e==="end"?(this._anchor||(this._anchor=this._doc.createComment("mat-drawer-anchor"),i.insertBefore(this._anchor,t)),i.appendChild(t)):this._anchor&&this._anchor.parentNode.insertBefore(t,this._anchor)}_handleTransitionEvent=e=>{let t=this._elementRef.nativeElement;e.target===t&&this._ngZone.run(()=>{e.type==="transitionend"&&this._setIsAnimating(!1),this._animationEnd.next(e)})};static \u0275fac=function(t){return new(t||n)};static \u0275cmp=h({type:n,selectors:[["mat-drawer"]],viewQuery:function(t,i){if(t&1&&ve(di,5),t&2){let o;M(o=C())&&(i._content=o.first)}},hostAttrs:[1,"mat-drawer"],hostVars:12,hostBindings:function(t,i){t&2&&(O("align",null)("tabIndex",i.mode!=="side"?"-1":null),Ne("visibility",!i._container&&!i.opened?"hidden":null),f("mat-drawer-end",i.position==="end")("mat-drawer-over",i.mode==="over")("mat-drawer-push",i.mode==="push")("mat-drawer-side",i.mode==="side"))},inputs:{position:"position",mode:"mode",disableClose:"disableClose",autoFocus:"autoFocus",opened:"opened"},outputs:{openedChange:"openedChange",_openedStream:"opened",openedStart:"openedStart",_closedStream:"closed",closedStart:"closedStart",onPositionChanged:"positionChanged"},exportAs:["matDrawer"],ngContentSelectors:Ze,decls:3,vars:0,consts:[["content",""],["cdkScrollable","",1,"mat-drawer-inner-container"]],template:function(t,i){t&1&&(E(),d(0,"div",1,0),g(2),c())},dependencies:[me],encapsulation:2,changeDetection:0})}return n})(),_t=(()=>{class n{_dir=a(Ue,{optional:!0});_element=a(k);_ngZone=a(j);_changeDetectorRef=a(Y);_animationDisabled=ae();_transitionsEnabled=!1;_allDrawers;_drawers=new Oe;_content;_userContent;get start(){return this._start}get end(){return this._end}get autosize(){return this._autosize}set autosize(e){this._autosize=ie(e)}_autosize=a(vi);get hasBackdrop(){return this._drawerHasBackdrop(this._start)||this._drawerHasBackdrop(this._end)}set hasBackdrop(e){this._backdropOverride=e==null?null:ie(e)}_backdropOverride=null;backdropClick=new V;_start=null;_end=null;_left=null;_right=null;_destroyed=new x;_doCheckSubject=new x;_contentMargins={left:null,right:null};_contentMarginChanges=new x;get scrollable(){return this._userContent||this._content}_injector=a($);constructor(){let e=a(ce),t=a(mt);this._dir?.change.pipe(D(this._destroyed)).subscribe(()=>{this._validateDrawers(),this.updateContentMargins()}),t.change().pipe(D(this._destroyed)).subscribe(()=>this.updateContentMargins()),!this._animationDisabled&&e.isBrowser&&this._ngZone.runOutsideAngular(()=>{setTimeout(()=>{this._element.nativeElement.classList.add("mat-drawer-transition"),this._transitionsEnabled=!0},200)})}ngAfterContentInit(){this._allDrawers.changes.pipe(B(this._allDrawers),D(this._destroyed)).subscribe(e=>{this._drawers.reset(e.filter(t=>!t._container||t._container===this)),this._drawers.notifyOnChanges()}),this._drawers.changes.pipe(B(null)).subscribe(()=>{this._validateDrawers(),this._drawers.forEach(e=>{this._watchDrawerToggle(e),this._watchDrawerPosition(e),this._watchDrawerMode(e)}),(!this._drawers.length||this._isDrawerOpen(this._start)||this._isDrawerOpen(this._end))&&this.updateContentMargins(),this._changeDetectorRef.markForCheck()}),this._ngZone.runOutsideAngular(()=>{this._doCheckSubject.pipe(Mt(10),D(this._destroyed)).subscribe(()=>this.updateContentMargins())})}ngOnDestroy(){this._contentMarginChanges.complete(),this._doCheckSubject.complete(),this._drawers.destroy(),this._destroyed.next(),this._destroyed.complete()}open(){this._drawers.forEach(e=>e.open())}close(){this._drawers.forEach(e=>e.close())}updateContentMargins(){let e=0,t=0;if(this._left&&this._left.opened){if(this._left.mode=="side")e+=this._left._getWidth();else if(this._left.mode=="push"){let i=this._left._getWidth();e+=i,t-=i}}if(this._right&&this._right.opened){if(this._right.mode=="side")t+=this._right._getWidth();else if(this._right.mode=="push"){let i=this._right._getWidth();t+=i,e-=i}}e=e||null,t=t||null,(e!==this._contentMargins.left||t!==this._contentMargins.right)&&(this._contentMargins={left:e,right:t},this._ngZone.run(()=>this._contentMarginChanges.next(this._contentMargins)))}ngDoCheck(){this._autosize&&this._isPushed()&&this._ngZone.runOutsideAngular(()=>this._doCheckSubject.next())}_watchDrawerToggle(e){e._animationStarted.pipe(D(this._drawers.changes)).subscribe(()=>{this.updateContentMargins(),this._changeDetectorRef.markForCheck()}),e.mode!=="side"&&e.openedChange.pipe(D(this._drawers.changes)).subscribe(()=>this._setContainerClass(e.opened))}_watchDrawerPosition(e){e.onPositionChanged.pipe(D(this._drawers.changes)).subscribe(()=>{be({read:()=>this._validateDrawers()},{injector:this._injector})})}_watchDrawerMode(e){e._modeChanged.pipe(D(re(this._drawers.changes,this._destroyed))).subscribe(()=>{this.updateContentMargins(),this._changeDetectorRef.markForCheck()})}_setContainerClass(e){let t=this._element.nativeElement.classList,i="mat-drawer-container-has-open";e?t.add(i):t.remove(i)}_validateDrawers(){this._start=this._end=null,this._drawers.forEach(e=>{e.position=="end"?(this._end!=null,this._end=e):(this._start!=null,this._start=e)}),this._right=this._left=null,this._dir&&this._dir.value==="rtl"?(this._left=this._end,this._right=this._start):(this._left=this._start,this._right=this._end)}_isPushed(){return this._isDrawerOpen(this._start)&&this._start.mode!="over"||this._isDrawerOpen(this._end)&&this._end.mode!="over"}_onBackdropClicked(){this.backdropClick.emit(),this._closeModalDrawersViaBackdrop()}_closeModalDrawersViaBackdrop(){[this._start,this._end].filter(e=>e&&!e.disableClose&&this._drawerHasBackdrop(e)).forEach(e=>e._closeViaBackdropClick())}_isShowingBackdrop(){return this._isDrawerOpen(this._start)&&this._drawerHasBackdrop(this._start)||this._isDrawerOpen(this._end)&&this._drawerHasBackdrop(this._end)}_isDrawerOpen(e){return e!=null&&e.opened}_drawerHasBackdrop(e){return this._backdropOverride==null?!!e&&e.mode!=="side":this._backdropOverride}static \u0275fac=function(t){return new(t||n)};static \u0275cmp=h({type:n,selectors:[["mat-drawer-container"]],contentQueries:function(t,i,o){if(t&1&&te(o,We,5)(o,ft,5),t&2){let l;M(l=C())&&(i._content=l.first),M(l=C())&&(i._allDrawers=l)}},viewQuery:function(t,i){if(t&1&&ve(We,5),t&2){let o;M(o=C())&&(i._userContent=o.first)}},hostAttrs:[1,"mat-drawer-container"],hostVars:2,hostBindings:function(t,i){t&2&&f("mat-drawer-container-explicit-backdrop",i._backdropOverride)},inputs:{autosize:"autosize",hasBackdrop:"hasBackdrop"},outputs:{backdropClick:"backdropClick"},exportAs:["matDrawerContainer"],features:[G([{provide:bt,useExisting:n}])],ngContentSelectors:mi,decls:4,vars:2,consts:[[1,"mat-drawer-backdrop",3,"mat-drawer-shown"],[1,"mat-drawer-backdrop",3,"click"]],template:function(t,i){t&1&&(E(ci),P(0,pi,1,2,"div",0),g(1),g(2,1),P(3,ui,2,0,"mat-drawer-content")),t&2&&(A(i.hasBackdrop?0:-1),u(3),A(i._content?-1:3))},dependencies:[We],styles:[`.mat-drawer-container {
  position: relative;
  z-index: 1;
  color: var(--mat-sidenav-content-text-color, var(--mat-sys-on-background));
  background-color: var(--mat-sidenav-content-background-color, var(--mat-sys-background));
  box-sizing: border-box;
  display: block;
  overflow: hidden;
}
.mat-drawer-container[fullscreen] {
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  position: absolute;
}
.mat-drawer-container[fullscreen].mat-drawer-container-has-open {
  overflow: hidden;
}
.mat-drawer-container.mat-drawer-container-explicit-backdrop .mat-drawer-side {
  z-index: 3;
}
.mat-drawer-container.ng-animate-disabled .mat-drawer-backdrop,
.mat-drawer-container.ng-animate-disabled .mat-drawer-content, .ng-animate-disabled .mat-drawer-container .mat-drawer-backdrop,
.ng-animate-disabled .mat-drawer-container .mat-drawer-content {
  transition: none;
}

.mat-drawer-backdrop {
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  position: absolute;
  display: block;
  z-index: 3;
  visibility: hidden;
}
.mat-drawer-backdrop.mat-drawer-shown {
  visibility: visible;
  background-color: var(--mat-sidenav-scrim-color, color-mix(in srgb, var(--mat-sys-neutral-variant20) 40%, transparent));
}
.mat-drawer-transition .mat-drawer-backdrop {
  transition-duration: 400ms;
  transition-timing-function: cubic-bezier(0.25, 0.8, 0.25, 1);
  transition-property: background-color, visibility;
}
@media (forced-colors: active) {
  .mat-drawer-backdrop {
    opacity: 0.5;
  }
}

.mat-drawer-content {
  position: relative;
  z-index: 1;
  display: block;
  height: 100%;
  overflow: auto;
}
.mat-drawer-content.mat-drawer-content-hidden {
  opacity: 0;
}
.mat-drawer-transition .mat-drawer-content {
  transition-duration: 400ms;
  transition-timing-function: cubic-bezier(0.25, 0.8, 0.25, 1);
  transition-property: transform, margin-left, margin-right;
}

.mat-drawer {
  position: relative;
  z-index: 4;
  color: var(--mat-sidenav-container-text-color, var(--mat-sys-on-surface-variant));
  box-shadow: var(--mat-sidenav-container-elevation-shadow, none);
  background-color: var(--mat-sidenav-container-background-color, var(--mat-sys-surface));
  border-top-right-radius: var(--mat-sidenav-container-shape, var(--mat-sys-corner-large));
  border-bottom-right-radius: var(--mat-sidenav-container-shape, var(--mat-sys-corner-large));
  width: var(--mat-sidenav-container-width, 360px);
  display: block;
  position: absolute;
  top: 0;
  bottom: 0;
  z-index: 3;
  outline: 0;
  box-sizing: border-box;
  overflow-y: auto;
  transform: translate3d(-100%, 0, 0);
}
@media (forced-colors: active) {
  .mat-drawer, [dir=rtl] .mat-drawer.mat-drawer-end {
    border-right: solid 1px currentColor;
  }
}
@media (forced-colors: active) {
  [dir=rtl] .mat-drawer, .mat-drawer.mat-drawer-end {
    border-left: solid 1px currentColor;
    border-right: none;
  }
}
.mat-drawer.mat-drawer-side {
  z-index: 2;
}
.mat-drawer.mat-drawer-end {
  right: 0;
  transform: translate3d(100%, 0, 0);
  border-top-left-radius: var(--mat-sidenav-container-shape, var(--mat-sys-corner-large));
  border-bottom-left-radius: var(--mat-sidenav-container-shape, var(--mat-sys-corner-large));
  border-top-right-radius: 0;
  border-bottom-right-radius: 0;
}
[dir=rtl] .mat-drawer {
  border-top-left-radius: var(--mat-sidenav-container-shape, var(--mat-sys-corner-large));
  border-bottom-left-radius: var(--mat-sidenav-container-shape, var(--mat-sys-corner-large));
  border-top-right-radius: 0;
  border-bottom-right-radius: 0;
  transform: translate3d(100%, 0, 0);
}
[dir=rtl] .mat-drawer.mat-drawer-end {
  border-top-right-radius: var(--mat-sidenav-container-shape, var(--mat-sys-corner-large));
  border-bottom-right-radius: var(--mat-sidenav-container-shape, var(--mat-sys-corner-large));
  border-top-left-radius: 0;
  border-bottom-left-radius: 0;
  left: 0;
  right: auto;
  transform: translate3d(-100%, 0, 0);
}
.mat-drawer-transition .mat-drawer {
  transition: transform 400ms cubic-bezier(0.25, 0.8, 0.25, 1);
}
.mat-drawer:not(.mat-drawer-opened):not(.mat-drawer-animating) {
  visibility: hidden;
  box-shadow: none;
}
.mat-drawer:not(.mat-drawer-opened):not(.mat-drawer-animating) .mat-drawer-inner-container {
  display: none;
}
.mat-drawer.mat-drawer-opened.mat-drawer-opened {
  transform: none;
}

.mat-drawer-side {
  box-shadow: none;
  border-right-color: var(--mat-sidenav-container-divider-color, transparent);
  border-right-width: 1px;
  border-right-style: solid;
}
.mat-drawer-side.mat-drawer-end {
  border-left-color: var(--mat-sidenav-container-divider-color, transparent);
  border-left-width: 1px;
  border-left-style: solid;
  border-right: none;
}
[dir=rtl] .mat-drawer-side {
  border-left-color: var(--mat-sidenav-container-divider-color, transparent);
  border-left-width: 1px;
  border-left-style: solid;
  border-right: none;
}
[dir=rtl] .mat-drawer-side.mat-drawer-end {
  border-right-color: var(--mat-sidenav-container-divider-color, transparent);
  border-right-width: 1px;
  border-right-style: solid;
  border-left: none;
}

.mat-drawer-inner-container {
  width: 100%;
  height: 100%;
  overflow: auto;
}

.mat-sidenav-fixed {
  position: fixed;
}
`],encapsulation:2,changeDetection:0})}return n})(),Xe=(()=>{class n extends We{static \u0275fac=(()=>{let e;return function(i){return(e||(e=le(n)))(i||n)}})();static \u0275cmp=h({type:n,selectors:[["mat-sidenav-content"]],hostAttrs:[1,"mat-drawer-content","mat-sidenav-content"],features:[G([{provide:me,useExisting:n}]),ee],ngContentSelectors:Ze,decls:1,vars:0,template:function(t,i){t&1&&(E(),g(0))},encapsulation:2,changeDetection:0})}return n})(),vt=(()=>{class n extends ft{get fixedInViewport(){return this._fixedInViewport}set fixedInViewport(e){this._fixedInViewport=ie(e)}_fixedInViewport=!1;get fixedTopGap(){return this._fixedTopGap}set fixedTopGap(e){this._fixedTopGap=dt(e)}_fixedTopGap=0;get fixedBottomGap(){return this._fixedBottomGap}set fixedBottomGap(e){this._fixedBottomGap=dt(e)}_fixedBottomGap=0;static \u0275fac=(()=>{let e;return function(i){return(e||(e=le(n)))(i||n)}})();static \u0275cmp=h({type:n,selectors:[["mat-sidenav"]],hostAttrs:[1,"mat-drawer","mat-sidenav"],hostVars:16,hostBindings:function(t,i){t&2&&(O("tabIndex",i.mode!=="side"?"-1":null)("align",null),Ne("top",i.fixedInViewport?i.fixedTopGap:null,"px")("bottom",i.fixedInViewport?i.fixedBottomGap:null,"px"),f("mat-drawer-end",i.position==="end")("mat-drawer-over",i.mode==="over")("mat-drawer-push",i.mode==="push")("mat-drawer-side",i.mode==="side")("mat-sidenav-fixed",i.fixedInViewport))},inputs:{fixedInViewport:"fixedInViewport",fixedTopGap:"fixedTopGap",fixedBottomGap:"fixedBottomGap"},exportAs:["matSidenav"],features:[G([{provide:ft,useExisting:n}]),ee],ngContentSelectors:Ze,decls:3,vars:0,consts:[["content",""],["cdkScrollable","",1,"mat-drawer-inner-container"]],template:function(t,i){t&1&&(E(),d(0,"div",1,0),g(2),c())},dependencies:[me],encapsulation:2,changeDetection:0})}return n})(),Nn=(()=>{class n extends _t{_allDrawers=void 0;_content=void 0;static \u0275fac=(()=>{let e;return function(i){return(e||(e=le(n)))(i||n)}})();static \u0275cmp=h({type:n,selectors:[["mat-sidenav-container"]],contentQueries:function(t,i,o){if(t&1&&te(o,Xe,5)(o,vt,5),t&2){let l;M(l=C())&&(i._content=l.first),M(l=C())&&(i._allDrawers=l)}},hostAttrs:[1,"mat-drawer-container","mat-sidenav-container"],hostVars:2,hostBindings:function(t,i){t&2&&f("mat-drawer-container-explicit-backdrop",i._backdropOverride)},exportAs:["matSidenavContainer"],features:[G([{provide:bt,useExisting:n},{provide:_t,useExisting:n}]),ee],ngContentSelectors:gi,decls:4,vars:2,consts:[[1,"mat-drawer-backdrop",3,"mat-drawer-shown"],[1,"mat-drawer-backdrop",3,"click"]],template:function(t,i){t&1&&(E(hi),P(0,fi,1,2,"div",0),g(1),g(2,1),P(3,_i,2,0,"mat-sidenav-content")),t&2&&(A(i.hasBackdrop?0:-1),u(3),A(i._content?-1:3))},dependencies:[Xe],styles:[bi],encapsulation:2,changeDetection:0})}return n})(),Ln=(()=>{class n{static \u0275fac=function(t){return new(t||n)};static \u0275mod=H({type:n});static \u0275inj=N({imports:[Ee,Q,Ee]})}return n})();var wi=["*",[["mat-toolbar-row"]]],Mi=["*","mat-toolbar-row"],Ci=(()=>{class n{static \u0275fac=function(t){return new(t||n)};static \u0275dir=J({type:n,selectors:[["mat-toolbar-row"]],hostAttrs:[1,"mat-toolbar-row"],exportAs:["matToolbarRow"]})}return n})(),zn=(()=>{class n{_elementRef=a(k);_platform=a(ce);_document=a(z);color;_toolbarRows;constructor(){}ngAfterViewInit(){this._platform.isBrowser&&(this._checkToolbarMixedModes(),this._toolbarRows.changes.subscribe(()=>this._checkToolbarMixedModes()))}_checkToolbarMixedModes(){this._toolbarRows.length}static \u0275fac=function(t){return new(t||n)};static \u0275cmp=h({type:n,selectors:[["mat-toolbar"]],contentQueries:function(t,i,o){if(t&1&&te(o,Ci,5),t&2){let l;M(l=C())&&(i._toolbarRows=l)}},hostAttrs:[1,"mat-toolbar"],hostVars:6,hostBindings:function(t,i){t&2&&(Le(i.color?"mat-"+i.color:""),f("mat-toolbar-multiple-rows",i._toolbarRows.length>0)("mat-toolbar-single-row",i._toolbarRows.length===0))},inputs:{color:"color"},exportAs:["matToolbar"],ngContentSelectors:Mi,decls:2,vars:0,template:function(t,i){t&1&&(E(wi),g(0),g(1,1))},styles:[`.mat-toolbar {
  background: var(--mat-toolbar-container-background-color, var(--mat-sys-surface));
  color: var(--mat-toolbar-container-text-color, var(--mat-sys-on-surface));
}
.mat-toolbar, .mat-toolbar h1, .mat-toolbar h2, .mat-toolbar h3, .mat-toolbar h4, .mat-toolbar h5, .mat-toolbar h6 {
  font-family: var(--mat-toolbar-title-text-font, var(--mat-sys-title-large-font));
  font-size: var(--mat-toolbar-title-text-size, var(--mat-sys-title-large-size));
  line-height: var(--mat-toolbar-title-text-line-height, var(--mat-sys-title-large-line-height));
  font-weight: var(--mat-toolbar-title-text-weight, var(--mat-sys-title-large-weight));
  letter-spacing: var(--mat-toolbar-title-text-tracking, var(--mat-sys-title-large-tracking));
  margin: 0;
}
@media (forced-colors: active) {
  .mat-toolbar {
    outline: solid 1px;
  }
}
.mat-toolbar .mat-form-field-underline,
.mat-toolbar .mat-form-field-ripple,
.mat-toolbar .mat-focused .mat-form-field-ripple {
  background-color: currentColor;
}
.mat-toolbar .mat-form-field-label,
.mat-toolbar .mat-focused .mat-form-field-label,
.mat-toolbar .mat-select-value,
.mat-toolbar .mat-select-arrow,
.mat-toolbar .mat-form-field.mat-focused .mat-select-arrow {
  color: inherit;
}
.mat-toolbar .mat-input-element {
  caret-color: currentColor;
}
.mat-toolbar .mat-mdc-button-base.mat-mdc-button-base.mat-unthemed {
  --mat-button-text-label-text-color: var(--mat-toolbar-container-text-color, var(--mat-sys-on-surface));
  --mat-button-outlined-label-text-color: var(--mat-toolbar-container-text-color, var(--mat-sys-on-surface));
}

.mat-toolbar-row, .mat-toolbar-single-row {
  display: flex;
  box-sizing: border-box;
  padding: 0 16px;
  width: 100%;
  flex-direction: row;
  align-items: center;
  white-space: nowrap;
  height: var(--mat-toolbar-standard-height, 64px);
}
@media (max-width: 599px) {
  .mat-toolbar-row, .mat-toolbar-single-row {
    height: var(--mat-toolbar-mobile-height, 56px);
  }
}

.mat-toolbar-multiple-rows {
  display: flex;
  box-sizing: border-box;
  flex-direction: column;
  width: 100%;
  min-height: var(--mat-toolbar-standard-height, 64px);
}
@media (max-width: 599px) {
  .mat-toolbar-multiple-rows {
    min-height: var(--mat-toolbar-mobile-height, 56px);
  }
}
`],encapsulation:2,changeDetection:0})}return n})();var Vn=(()=>{class n{static \u0275fac=function(t){return new(t||n)};static \u0275mod=H({type:n});static \u0275inj=N({imports:[Q]})}return n})();var qe=class n{api=a(sn);list=(r=!1)=>this.api.get("/notifications",{unread_only:r,page_size:20});unreadCount=()=>this.api.get("/notifications/unread-count");markRead=r=>this.api.post(`/notifications/${r}/read`);markAll=()=>this.api.post("/notifications/read-all");static \u0275fac=function(e){return new(e||n)};static \u0275prov=Ie({token:n,factory:n.\u0275fac,providedIn:"root"})};var Ei=(n,r)=>r.title,Pi=(n,r)=>r.id,Ai=(n,r)=>r.route;function Si(n,r){if(n&1){let e=R();d(0,"a",36,3),_("click",function(){y(e);let i=b(2),o=ne(2);return w(i.isHandset()&&o.close())}),d(2,"mat-icon",37),p(3),c(),d(4,"span",38),p(5),c()()}if(n&2){let e=r.$implicit,t=ne(1);U("routerLink",e.route)("activated",t.isActive),O("aria-current",t.isActive?"page":null),u(3),T(e.icon),u(2),T(e.label)}}function Ri(n,r){if(n&1&&(d(0,"div",34),p(1),c(),d(2,"mat-nav-list"),Fe(3,Si,6,5,"a",35,Ai),c()),n&2){let e=r.$implicit;u(),T(e.title),u(2),Be(e.items)}}function Ti(n,r){if(n&1){let e=R();d(0,"button",39),_("click",function(){y(e),b();let i=ne(2);return w(i.toggle())}),d(1,"mat-icon"),p(2,"menu"),c()(),d(3,"span",40),p(4,"Carbon"),d(5,"b"),p(6,"Platform"),c()()}}function Ii(n,r){n&1&&(d(0,"span",13),p(1,"DEMO"),c())}function Oi(n,r){if(n&1){let e=R();d(0,"button",41),_("click",function(){y(e);let i=b();return w(i.markAllRead())}),p(1,"Mark all read"),c()}}function Fi(n,r){if(n&1){let e=R();d(0,"button",32),_("click",function(){let i=y(e).$implicit,o=b();return w(o.openNotification(i))}),d(1,"span",42),p(2),c(),d(3,"span",43),p(4),Ot(5,"date"),c()()}if(n&2){let e=r.$implicit;f("unread",!e.read_at),u(2),T(e.title),u(2),T(Ft(5,4,e.created_at,"short"))}}function Bi(n,r){n&1&&(d(0,"div",20)(1,"small"),p(2,"No notifications."),c()())}var $e=class n{auth=a(I);notificationsApi=a(qe);router=a(oe);destroyRef=a(xt);unread=K(0);notifications=K([]);isHandset=dn(a(Gt).observe("(max-width: 900px)").pipe(_e(r=>r.matches)),{initialValue:!1});nav=ye(()=>{let r=this.auth.permissions();return En(kn,e=>r.has(e))});initials=ye(()=>(this.auth.user()?.full_name??"?").split(/\s+/).map(r=>r[0]).slice(0,2).join("").toUpperCase());primaryRole=ye(()=>this.auth.user()?.roles?.[0]?.role_name??"No role");roleSummary=ye(()=>Array.from(new Set((this.auth.user()?.roles??[]).map(r=>r.role_name))).join(", ")||"No roles assigned");ngOnInit(){wt(0,6e4).pipe(q(()=>this.notificationsApi.unreadCount().pipe(se(()=>fe(null)))),ln(this.destroyRef)).subscribe(r=>r&&this.unread.set(r.unread))}openNotifications(){this.notificationsApi.list().pipe(B(null)).subscribe(r=>r&&this.notifications.set(r.items))}openNotification(r){r.read_at||this.notificationsApi.markRead(r.id).subscribe(()=>this.unread.update(e=>Math.max(0,e-1))),r.link&&this.router.navigateByUrl(r.link)}markAllRead(){this.notificationsApi.markAll().subscribe(()=>{this.unread.set(0),this.notifications.update(r=>r.map(e=>Se(ge({},e),{read_at:e.read_at??new Date().toISOString()})))})}signOut(){this.auth.logout().subscribe()}static \u0275fac=function(e){return new(e||n)};static \u0275cmp=h({type:n,selectors:[["app-shell"]],decls:65,vars:14,consts:[["drawer",""],["notifMenu","matMenu"],["userMenu","matMenu"],["rla","routerLinkActive"],[1,"shell"],[1,"sidenav",3,"mode","opened"],["routerLink","/dashboard",1,"brand",3,"click"],[1,"brand-text"],[1,"brand-name"],[1,"brand-tag"],["aria-label","Main"],[1,"topbar"],[1,"spacer"],["matTooltip","You are signed in with a DEMO account. Demo data is never mixed with real records.",1,"demo-flag"],["mat-icon-button","","type","button","aria-label","Notifications","matTooltip","Notifications",1,"bell",3,"menuOpened","matMenuTriggerFor"],["matBadgeSize","small","matBadgeColor","warn","aria-hidden","false",3,"matBadge"],["xPosition","before",1,"notif-menu"],[1,"menu-head","notif-head",3,"click"],["mat-button","","type","button"],["mat-menu-item","","type","button",3,"unread"],[1,"menu-head"],["aria-hidden","true",1,"divider"],["type","button","aria-label","Account menu",1,"user-chip",3,"matMenuTriggerFor"],[1,"avatar"],[1,"who"],[1,"user-name"],[1,"user-role"],[1,"chev"],["xPosition","before"],[1,"menu-head",3,"click"],["mat-menu-item","","routerLink","/profile"],["mat-menu-item","","routerLink","/change-password"],["mat-menu-item","","type","button",3,"click"],[1,"content","cp-content"],[1,"nav-section"],["mat-list-item","","routerLinkActive","active-link",1,"nav-item",3,"routerLink","activated"],["mat-list-item","","routerLinkActive","active-link",1,"nav-item",3,"click","routerLink","activated"],["matListItemIcon",""],["matListItemTitle",""],["mat-icon-button","","type","button","aria-label","Toggle navigation",3,"click"],[1,"mobile-brand"],["mat-button","","type","button",3,"click"],[1,"notif-title"],[1,"notif-time"]],template:function(e,t){if(e&1){let i=R();d(0,"mat-sidenav-container",4)(1,"mat-sidenav",5,0)(3,"a",6),_("click",function(){y(i);let l=ne(2);return w(t.isHandset()&&l.close())}),d(4,"span",7)(5,"span",8),p(6,"Carbon"),d(7,"b"),p(8,"Platform"),c()(),d(9,"span",9),p(10,"From soil to verified credit"),c()()(),d(11,"nav",10),Fe(12,Ri,5,1,null,null,Ei),c()(),d(14,"mat-sidenav-content")(15,"mat-toolbar",11),P(16,Ti,7,0),S(17,"span",12),P(18,Ii,2,0,"span",13),d(19,"button",14),_("menuOpened",function(){return t.openNotifications()}),d(20,"mat-icon",15),p(21,"notifications"),c()(),d(22,"mat-menu",16,1)(24,"div",17),_("click",function(l){return l.stopPropagation()}),d(25,"strong"),p(26,"Notifications"),c(),P(27,Oi,2,0,"button",18),c(),S(28,"mat-divider"),Fe(29,Fi,6,7,"button",19,Pi,!1,Bi,3,0,"div",20),c(),S(32,"span",21),d(33,"button",22)(34,"span",23),p(35),c(),d(36,"span",24)(37,"span",25),p(38),c(),d(39,"span",26),p(40),c()(),d(41,"mat-icon",27),p(42,"expand_more"),c()(),d(43,"mat-menu",28,2)(45,"div",29),_("click",function(l){return l.stopPropagation()}),d(46,"strong"),p(47),c(),d(48,"small"),p(49),c()(),S(50,"mat-divider"),d(51,"a",30)(52,"mat-icon"),p(53,"person"),c(),p(54,"My profile"),c(),d(55,"a",31)(56,"mat-icon"),p(57,"key"),c(),p(58,"Change password"),c(),d(59,"button",32),_("click",function(){return t.signOut()}),d(60,"mat-icon"),p(61,"logout"),c(),p(62,"Sign out"),c()()(),d(63,"main",33),S(64,"router-outlet"),c()()()}if(e&2){let i,o,l=ne(23),v=ne(44);u(),U("mode",t.isHandset()?"over":"side")("opened",!t.isHandset()),u(11),Be(t.nav()),u(4),A(t.isHandset()?16:-1),u(2),A(t.auth.isDemo()?18:-1),u(),U("matMenuTriggerFor",l),u(),U("matBadge",t.unread()||null),u(7),A(t.unread()?27:-1),u(2),Be(t.notifications()),u(4),U("matMenuTriggerFor",v),u(2),T(t.initials()),u(3),T((i=t.auth.user())==null?null:i.full_name),u(2),T(t.primaryRole()),u(7),T((o=t.auth.user())==null?null:o.email),u(2),T(t.roleSummary())}},dependencies:[Ge,Me,en,Ln,vt,Nn,Xe,Vn,zn,_n,fn,gn,hn,mn,un,ke,De,xe,Ce,cn,Bn,ue,Ae,Fn,pn,Dn,xn,Tn,Rn,Bt],styles:['.shell[_ngcontent-%COMP%]{height:100vh;background:var(--cp-mint)}.sidenav[_ngcontent-%COMP%]{width:260px;border:0;color:#dbe8df;background:var(--cp-forest-deep);--mat-sidenav-container-background-color: var(--cp-forest-deep);--mat-sidenav-container-shape: 0;--mat-list-active-indicator-color: transparent;--mat-list-list-item-label-text-font: var(--cp-font);--mat-list-list-item-label-text-size: 14px;--mat-list-list-item-label-text-weight: 400;--mat-list-list-item-one-line-container-height: 42px;--mat-list-list-item-label-text-color: #c3d5ca;--mat-list-list-item-hover-label-text-color: #ffffff;--mat-list-list-item-focus-label-text-color: #ffffff;--mat-list-list-item-leading-icon-color: #86a893;--mat-list-list-item-hover-leading-icon-color: #ffffff;--mat-list-list-item-focus-leading-icon-color: #ffffff;--mat-list-list-item-hover-state-layer-color: #ffffff;--mat-list-list-item-focus-state-layer-color: #ffffff;--mat-list-list-item-hover-state-layer-opacity: .06;--mat-list-list-item-focus-state-layer-opacity: .06}.sidenav[_ngcontent-%COMP%]     .mat-drawer-inner-container{display:flex;flex-direction:column}.brand[_ngcontent-%COMP%]{display:flex;align-items:center;height:72px;padding:0 24px;text-decoration:none;box-sizing:border-box;border-bottom:1px solid rgba(255,255,255,.07);flex:none}.brand-text[_ngcontent-%COMP%]{display:flex;flex-direction:column;gap:3px}.brand-name[_ngcontent-%COMP%]{font:300 19px/1 var(--cp-font);color:#fff;letter-spacing:-.02em}.brand-name[_ngcontent-%COMP%]   b[_ngcontent-%COMP%], .mobile-brand[_ngcontent-%COMP%]   b[_ngcontent-%COMP%]{font-weight:600;color:var(--cp-lime-2);margin-left:1px}.brand-tag[_ngcontent-%COMP%]{font:italic 400 12.5px/1.2 var(--cp-serif);color:#9dbba8}nav[_ngcontent-%COMP%]{flex:1;overflow-y:auto;padding:4px 14px 20px}.nav-section[_ngcontent-%COMP%]{padding:20px 12px 6px;font:600 10.5px var(--cp-font);letter-spacing:.14em;text-transform:uppercase;color:#6f9480}.sidenav[_ngcontent-%COMP%]   .nav-item[_ngcontent-%COMP%]{position:relative;border-radius:8px;margin:2px 0;transition:background-color .15s}.sidenav[_ngcontent-%COMP%]   .nav-item[_ngcontent-%COMP%]     .mdc-list-item__primary-text{transition:color .15s,transform .2s var(--cp-ease)}.sidenav[_ngcontent-%COMP%]   .nav-item[_ngcontent-%COMP%]:hover     .mdc-list-item__primary-text{transform:translate(2px)}.sidenav[_ngcontent-%COMP%]   .active-link[_ngcontent-%COMP%]{background:#ffffff17;--mat-list-list-item-label-text-color: #ffffff;--mat-list-list-item-hover-label-text-color: #ffffff;--mat-list-list-item-focus-label-text-color: #ffffff;--mat-list-list-item-leading-icon-color: var(--cp-lime-2);--mat-list-list-item-hover-leading-icon-color: var(--cp-lime-2);--mat-list-list-item-focus-leading-icon-color: var(--cp-lime-2);--mat-list-list-item-label-text-weight: 500}.sidenav[_ngcontent-%COMP%]   .active-link[_ngcontent-%COMP%]:after{content:"";position:absolute;left:0;top:11px;bottom:11px;width:3px;border-radius:0 3px 3px 0;background:var(--cp-lime);animation:_ngcontent-%COMP%_marker .25s var(--cp-ease) both}@keyframes _ngcontent-%COMP%_marker{0%{transform:scaleY(0)}to{transform:none}}.mobile-brand[_ngcontent-%COMP%]{font:300 17px var(--cp-font);color:var(--cp-forest);letter-spacing:-.02em;margin-left:4px}.mobile-brand[_ngcontent-%COMP%]   b[_ngcontent-%COMP%]{color:var(--cp-forest-3)}.topbar[_ngcontent-%COMP%]{position:sticky;top:0;z-index:3;height:64px;gap:4px;padding:0 20px 0 16px;background:#fff;border-bottom:1px solid var(--cp-line)}.spacer[_ngcontent-%COMP%]{flex:1}.demo-flag[_ngcontent-%COMP%]{margin-right:8px;padding:3px 10px;border-radius:6px;font:600 11px var(--cp-font);letter-spacing:.08em;background:#f4ecf7;color:#6a1b9a;border:1px solid #e3d0ec}.bell[_ngcontent-%COMP%]{color:var(--cp-ink-2)}.divider[_ngcontent-%COMP%]{width:1px;height:28px;background:var(--cp-line);margin:0 10px 0 6px}.user-chip[_ngcontent-%COMP%]{display:inline-flex;align-items:center;gap:10px;height:44px;padding:0 8px 0 4px;border:0;border-radius:10px;background:transparent;cursor:pointer;font:inherit;color:var(--cp-navy);transition:background-color .15s}.user-chip[_ngcontent-%COMP%]:hover, .user-chip[aria-expanded=true][_ngcontent-%COMP%]{background:var(--cp-mint)}.user-chip[_ngcontent-%COMP%]:focus-visible{outline:2px solid var(--cp-forest);outline-offset:2px}.avatar[_ngcontent-%COMP%]{display:inline-grid;place-items:center;width:34px;height:34px;border-radius:50%;flex:none;background:var(--cp-forest);color:#fff;font:600 13px var(--cp-font);letter-spacing:.02em}.who[_ngcontent-%COMP%]{display:flex;flex-direction:column;align-items:flex-start;line-height:1.25;text-align:left}.user-name[_ngcontent-%COMP%]{font:500 14px var(--cp-font);color:var(--cp-navy);max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.user-role[_ngcontent-%COMP%]{font:400 12px var(--cp-font);color:var(--cp-ink-2);max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.chev[_ngcontent-%COMP%]{color:var(--cp-ink-3);font-size:20px;width:20px;height:20px}.menu-head[_ngcontent-%COMP%]{display:flex;flex-direction:column;gap:2px;padding:10px 16px;max-width:280px}.menu-head[_ngcontent-%COMP%]   small[_ngcontent-%COMP%]{color:var(--cp-ink-2)}.content[_ngcontent-%COMP%]{padding:28px 32px 48px;max-width:1440px;margin:0 auto;view-transition-name:cp-content;box-sizing:border-box}@media(max-width:600px){.content[_ngcontent-%COMP%]{padding:16px}.who[_ngcontent-%COMP%], .divider[_ngcontent-%COMP%]{display:none}}.notif-head[_ngcontent-%COMP%]{flex-direction:row;align-items:center;justify-content:space-between;min-width:300px}.notif-title[_ngcontent-%COMP%]{display:block;max-width:320px;white-space:normal;line-height:1.3}.notif-time[_ngcontent-%COMP%]{display:block;font-size:11px;color:var(--cp-ink-2)}.unread[_ngcontent-%COMP%]   .notif-title[_ngcontent-%COMP%]{font-weight:600}'],changeDetection:0})};var Ke=class n{static \u0275fac=function(e){return new(e||n)};static \u0275cmp=h({type:n,selectors:[["app-forbidden-page"]],decls:9,vars:0,consts:[[1,"centered"],[1,"big"],["mat-flat-button","","routerLink","/dashboard"]],template:function(e,t){e&1&&(d(0,"section",0)(1,"mat-icon",1),p(2,"lock"),c(),d(3,"h1"),p(4,"You don't have access to this page"),c(),d(5,"p"),p(6,"Your roles do not include the permission it needs. Ask a Platform Admin if you think this is wrong."),c(),d(7,"a",2),p(8,"Back to dashboard"),c()())},dependencies:[Me,xe,Ce,ke,De],encapsulation:2,changeDetection:0})},Je=class n{static \u0275fac=function(e){return new(e||n)};static \u0275cmp=h({type:n,selectors:[["app-not-found-page"]],decls:9,vars:0,consts:[[1,"centered"],[1,"big"],["mat-flat-button","","routerLink","/dashboard"]],template:function(e,t){e&1&&(d(0,"section",0)(1,"mat-icon",1),p(2,"search_off"),c(),d(3,"h1"),p(4,"Page not found"),c(),d(5,"p"),p(6,"The address may be mistyped, or the record no longer exists."),c(),d(7,"a",2),p(8,"Back to dashboard"),c()())},dependencies:[Me,xe,Ce,ke,De],encapsulation:2,changeDetection:0})};var Hn=[{path:"login",canActivate:[Pn],title:"Sign in",loadComponent:()=>import("./chunk-S6UYP2KJ.js").then(n=>n.LoginPage)},{path:"change-password",canActivate:[pt],title:"Change password",loadComponent:()=>import("./chunk-KSBDZDP7.js").then(n=>n.ChangePasswordPage)},{path:"",component:$e,canActivate:[pt],canActivateChild:[An],children:[{path:"",pathMatch:"full",redirectTo:"dashboard"},{path:"dashboard",title:"Dashboard",loadComponent:()=>import("./chunk-VRN4UPBQ.js").then(n=>n.DashboardPage)},{path:"profile",title:"My profile",loadComponent:()=>import("./chunk-2BQOXIW7.js").then(n=>n.ProfilePage)},{path:"farmers",canActivate:[m],data:{anyPermissions:[s.FARMERS_READ,s.FARMERS_SELF]},children:[{path:"",title:"Farmers",loadComponent:()=>import("./chunk-YCQR5YKY.js").then(n=>n.FarmersListPage)},{path:"new",title:"Register farmer",canActivate:[m],data:{permissions:[s.FARMERS_MANAGE]},loadComponent:()=>import("./chunk-D47GDOJR.js").then(n=>n.FarmerCreatePage)},{path:":id",title:"Farmer",loadComponent:()=>import("./chunk-4U3AHLDJ.js").then(n=>n.FarmerDetailPage)}]},{path:"me/farmer",title:"My farmer profile",canActivate:[m],data:{permissions:[s.FARMERS_SELF]},loadComponent:()=>import("./chunk-YMS3UEEH.js").then(n=>n.MyFarmerPage)},{path:"farms",canActivate:[m],data:{anyPermissions:[s.FARMS_READ,s.FARMERS_SELF]},children:[{path:"",title:"Farms",loadComponent:()=>import("./chunk-5WHJTCQI.js").then(n=>n.FarmsListPage)},{path:"new",title:"Add farm",canActivate:[m],data:{anyPermissions:[s.FARMS_MANAGE,s.FARMERS_SELF]},loadComponent:()=>import("./chunk-27RLYUXY.js").then(n=>n.FarmCreatePage)},{path:":id",title:"Farm",loadComponent:()=>import("./chunk-V5FW2R5H.js").then(n=>n.FarmDetailPage)}]},{path:"projects",canActivate:[m],data:{permissions:[s.PROJECTS_READ]},children:[{path:"",title:"Projects",loadComponent:()=>import("./chunk-B2RHUF6H.js").then(n=>n.ProjectsListPage)},{path:"new",title:"New project",canActivate:[m],data:{permissions:[s.PROJECTS_MANAGE]},loadComponent:()=>import("./chunk-VSWDKV2S.js").then(n=>n.ProjectCreatePage)},{path:":id",title:"Project",loadComponent:()=>import("./chunk-TIU57A2I.js").then(n=>n.ProjectDetailPage)}]},{path:"methodologies",canActivate:[m],data:{permissions:[s.METHODOLOGIES_READ]},children:[{path:"",title:"Methodologies",loadComponent:()=>import("./chunk-WM3EYIUS.js").then(n=>n.MethodologiesPage)},{path:"versions/:id",title:"Methodology version",loadComponent:()=>import("./chunk-GLAOU2U4.js").then(n=>n.MethodologyVersionPage)}]},{path:"mrv",canActivate:[m],data:{permissions:[s.MRV_READ]},children:[{path:"",title:"MRV",loadComponent:()=>import("./chunk-GZSX2GUO.js").then(n=>n.MrvDashboardPage)},{path:"projects/:id",title:"MRV workspace",loadComponent:()=>import("./chunk-4YULGA7W.js").then(n=>n.MrvProjectPage)},{path:"projects/:id/plans/new",title:"New MRV plan",canActivate:[m],data:{permissions:[s.MRV_MANAGE]},loadComponent:()=>import("./chunk-N3VAYKZA.js").then(n=>n.MrvPlanCreatePage)},{path:"plans/:id",title:"MRV plan",loadComponent:()=>import("./chunk-WEFCLBFP.js").then(n=>n.MrvPlanDetailPage)},{path:"datasets/:id",title:"MRV dataset",loadComponent:()=>import("./chunk-ZSWYDTEA.js").then(n=>n.MrvDatasetPage)},{path:"samples/:id",title:"Sample",canActivate:[m],data:{permissions:[s.LAB_READ]},loadComponent:()=>import("./chunk-XY7RASLB.js").then(n=>n.SampleDetailPage)},{path:"lab-results/:id",title:"Laboratory result",canActivate:[m],data:{permissions:[s.LAB_READ]},loadComponent:()=>import("./chunk-P3JXNME3.js").then(n=>n.LabResultLineagePage)}]},{path:"calculations",title:"Calculations",canActivate:[m],data:{permissions:[s.CALCULATION_READ]},loadComponent:()=>import("./chunk-2ZUI67TX.js").then(n=>n.CalculationsPage)},{path:"calculations/runs/:id",title:"Calculation run",canActivate:[m],data:{permissions:[s.CALCULATION_READ]},loadComponent:()=>import("./chunk-YXGC2RQG.js").then(n=>n.CalculationRunPage)},{path:"registry",title:"Registry",canActivate:[m],data:{permissions:[s.REGISTRY_READ]},loadComponent:()=>import("./chunk-2PGVLQ2N.js").then(n=>n.RegistryPage)},{path:"credits",title:"Issued credits",canActivate:[m],data:{permissions:[s.CREDITS_READ]},loadComponent:()=>import("./chunk-TD6UMUAU.js").then(n=>n.CreditsPage)},{path:"ledger",title:"Credit ledger",canActivate:[m],data:{permissions:[s.CREDITS_READ]},loadComponent:()=>import("./chunk-MUO34LVZ.js").then(n=>n.LedgerPage)},{path:"holdings",title:"My credits",canActivate:[m],data:{permissions:[s.CREDITS_HOLDER_READ]},loadComponent:()=>import("./chunk-TMXLOZHA.js").then(n=>n.HoldingsPage)},{path:"marketplace",children:[{path:"",title:"Marketplace",canActivate:[m],data:{permissions:[s.MARKETPLACE_READ]},loadComponent:()=>import("./chunk-R5FOEOHI.js").then(n=>n.MarketplacePage)},{path:"listings",title:"Listings",canActivate:[m],data:{anyPermissions:[s.LISTINGS_MANAGE,s.LISTINGS_APPROVE]},loadComponent:()=>import("./chunk-QX4HBVZE.js").then(n=>n.ListingsPage)},{path:"profile",title:"Buyer profile",canActivate:[m],data:{permissions:[s.BUYERS_KYC_SUBMIT]},loadComponent:()=>import("./chunk-YENSI3QD.js").then(n=>n.BuyerProfilePage)},{path:"kyc-review",title:"KYC review",canActivate:[m],data:{permissions:[s.BUYERS_KYC_VERIFY]},loadComponent:()=>import("./chunk-FLPJ3YQQ.js").then(n=>n.KycReviewPage)}]},{path:"orders",title:"Orders",canActivate:[m],data:{anyPermissions:[s.ORDERS_READ,s.ORDERS_PLACE]},loadComponent:()=>import("./chunk-35XMK57C.js").then(n=>n.OrdersPage)},{path:"payments",title:"Payments",canActivate:[m],data:{anyPermissions:[s.PAYMENTS_CONFIRM,s.REFUNDS_REQUEST,s.REFUNDS_APPROVE]},loadComponent:()=>import("./chunk-OAJK5VXA.js").then(n=>n.PaymentsPage)},{path:"vvb",canActivate:[m],data:{permissions:[s.VERIFICATION_VVB_READ]},children:[{path:"",title:"VVB workspace",loadComponent:()=>import("./chunk-ISEFFJ3U.js").then(n=>n.VvbWorkspacePage)},{path:"assignments/:id",title:"VVB assignment",loadComponent:()=>import("./chunk-XS473XDP.js").then(n=>n.VvbAssignmentPage)}]},{path:"laboratory",canActivate:[m],data:{permissions:[s.LAB_LAB_READ]},children:[{path:"",title:"Laboratory",loadComponent:()=>import("./chunk-BQQG6RE7.js").then(n=>n.LaboratoryPage)},{path:"tests/:id",title:"Laboratory test",loadComponent:()=>import("./chunk-OMGFFLUE.js").then(n=>n.LabTestPage)},{path:"qa/:id",title:"Laboratory QA",canActivate:[m],data:{permissions:[s.LAB_QA]},loadComponent:()=>import("./chunk-5P5ROAHU.js").then(n=>n.LabQaPage)}]},{path:"field",canActivate:[m],data:{permissions:[s.SAMPLING_COLLECT]},children:[{path:"",title:"Field work",loadComponent:()=>import("./chunk-32BP64Y3.js").then(n=>n.FieldDashboardPage)},{path:"collections/:id",title:"Field collection",loadComponent:()=>import("./chunk-SCUO4HTY.js").then(n=>n.FieldCollectionPage)}]},{path:"me/projects",title:"My project participation",canActivate:[m],data:{permissions:[s.FARMERS_SELF]},loadComponent:()=>import("./chunk-AVDWD5MC.js").then(n=>n.MyParticipationPage)},{path:"me/payouts",title:"My payouts",canActivate:[m],data:{permissions:[s.FARMERS_SELF]},loadComponent:()=>import("./chunk-4RUUYKCS.js").then(n=>n.MyPayoutsPage)},{path:"finance",children:[{path:"",pathMatch:"full",redirectTo:"revenue"},{path:"revenue",title:"Revenue & costs",canActivate:[m],data:{anyPermissions:[s.REVENUE_READ,s.COSTS_MANAGE,s.COSTS_APPROVE]},loadComponent:()=>import("./chunk-PGX7U4I4.js").then(n=>n.RevenuePage)},{path:"sharing",title:"Revenue sharing",canActivate:[m],data:{anyPermissions:[s.SHARING_MANAGE,s.SHARING_APPROVE]},loadComponent:()=>import("./chunk-JPA4G3TS.js").then(n=>n.SharingPage)},{path:"settlements",title:"Settlements",canActivate:[m],data:{anyPermissions:[s.SETTLEMENT_READ,s.SETTLEMENT_CALCULATE,s.SETTLEMENT_APPROVE]},loadComponent:()=>import("./chunk-YB4XNEPL.js").then(n=>n.SettlementsPage)},{path:"payouts",title:"Payouts",canActivate:[m],data:{anyPermissions:[s.PAYOUTS_READ,s.PAYOUTS_CALCULATE,s.PAYOUTS_APPROVE,s.PAYOUTS_EXECUTE,s.PAYOUTS_RECONCILE]},loadComponent:()=>import("./chunk-RF5VL6PC.js").then(n=>n.PayoutsPage)}]},{path:"admin",children:[{path:"users",canActivate:[m],data:{permissions:[s.USERS_READ]},children:[{path:"",title:"Users",loadComponent:()=>import("./chunk-7UPSV3ZM.js").then(n=>n.UsersListPage)},{path:"new",title:"New user",canActivate:[m],data:{permissions:[s.USERS_MANAGE]},loadComponent:()=>import("./chunk-3XUPFDHT.js").then(n=>n.UserCreatePage)},{path:":id",title:"User",loadComponent:()=>import("./chunk-ATOWXPNZ.js").then(n=>n.UserDetailPage)}]},{path:"organizations",canActivate:[m],data:{permissions:[s.ORGANIZATIONS_READ]},children:[{path:"",title:"Organizations",loadComponent:()=>import("./chunk-X4CXT4JT.js").then(n=>n.OrganizationsListPage)},{path:":id",title:"Organization",loadComponent:()=>import("./chunk-CKFY3P7O.js").then(n=>n.OrganizationDetailPage)}]},{path:"roles",title:"Roles & permissions",canActivate:[m],data:{permissions:[s.ROLES_READ]},loadComponent:()=>import("./chunk-5WNYVGES.js").then(n=>n.RolesPage)},{path:"catalog",title:"Standards & activities",canActivate:[m],data:{permissions:[s.STANDARDS_MANAGE]},loadComponent:()=>import("./chunk-TW7UDSMA.js").then(n=>n.CatalogPage)},{path:"consents",title:"Consent types",canActivate:[m],data:{permissions:[s.CONSENTS_CONFIGURE]},loadComponent:()=>import("./chunk-WG4IMW6B.js").then(n=>n.ConsentDefinitionsPage)},{path:"audit",title:"Audit log",canActivate:[m],data:{permissions:[s.AUDIT_READ]},loadComponent:()=>import("./chunk-VLKZX3C7.js").then(n=>n.AuditPage)},{path:"security",title:"Security center",canActivate:[m],data:{permissions:[s.SECURITY_READ]},loadComponent:()=>import("./chunk-VIBEHCOD.js").then(n=>n.SecurityPage)},{path:"quarantine",title:"Document quarantine",canActivate:[m],data:{permissions:[s.SECURITY_READ]},loadComponent:()=>import("./chunk-OEYF6EMG.js").then(n=>n.QuarantinePage)},{path:"jobs",title:"Background jobs",canActivate:[m],data:{permissions:[s.JOBS_READ]},loadComponent:()=>import("./chunk-KBY3P7OC.js").then(n=>n.JobsPage)}]},{path:"forbidden",title:"No access",component:Ke},{path:"**",title:"Not found",component:Je}]}];var Ni=/\/auth\/(login|refresh|logout|token)$/,Un=(n,r)=>{if(!n.url.startsWith(rn))return r(n);let e=a(I),t=Ni.test(n.url),i=e.accessToken(),o=i&&!t?n.clone({setHeaders:{Authorization:`Bearer ${i}`}}):n;return r(o).pipe(se(l=>!(l instanceof lt)||l.status!==401||t||!i?X(()=>l):e.refresh().pipe(se(v=>(e.sessionEnded(),X(()=>v))),q(v=>r(n.clone({setHeaders:{Authorization:`Bearer ${v}`}}))))))},Gn=(n,r)=>r(n).pipe(se(e=>{if(!(e instanceof lt))return X(()=>Pe.from(e));if(e.status===0)return X(()=>new Pe(0,"NETWORK_ERROR","Cannot reach the server. Check your connection and try again."));let t=e.error;if(t&&typeof t=="object"&&typeof t.error_code=="string")return X(()=>new Pe(e.status,t.error_code,t.message??"Request failed.",t.details??{},t.request_id??null));let i=e.status>=500?"The server had a problem. Please try again.":"The request failed.";return X(()=>new Pe(e.status,"HTTP_ERROR",i,{},e.headers.get("X-Request-ID")))}));var et=class n extends Ye{title=a(Vt);updateTitle(r){let e=this.buildTitle(r);this.title.setTitle(e?`${e} \xB7 Carbon Platform`:"Carbon Platform")}static \u0275fac=(()=>{let r;return function(t){return(r||(r=le(n)))(t||n)}})();static \u0275prov=Ie({token:n,factory:n.\u0275fac})};var Yn={providers:[Dt(),tn(Hn,an(),nn({scrollPositionRestoration:"top"}),on({skipInitialTransition:!0})),Lt(zt([Gn,Un])),St(()=>a(I).restoreSession()),{provide:Ye,useClass:et},{provide:Jt,useValue:{appearance:"outline"}},{provide:Kt,useValue:{hideSingleSelectionIndicator:!0,hideMultipleSelectionIndicator:!0}}]};var tt=class n{static \u0275fac=function(e){return new(e||n)};static \u0275cmp=h({type:n,selectors:[["app-root"]],decls:1,vars:0,template:function(e,t){e&1&&S(0,"router-outlet")},dependencies:[Ge],encapsulation:2,changeDetection:0})};Nt(tt,Yn).catch(n=>console.error(n));
