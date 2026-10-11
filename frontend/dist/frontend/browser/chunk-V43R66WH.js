import{d as E,e as st,f as rt,h as R,r as ot,v as ct,x as lt}from"./chunk-CR2I6BNW.js";import{a as T}from"./chunk-CS36JUXR.js";import{G as at,I as D,P as it,e as Y,l as tt,q as et,v as nt}from"./chunk-MVNFUC75.js";import{$ as z,Aa as H,Ha as Z,Ia as Q,J as P,Ja as U,O as b,Pa as v,Q as g,Qa as f,R as o,Ra as W,Sb as J,T as F,U as N,X as h,Y as L,Ya as K,_a as x,ab as S,d as l,eb as X,fa as q,fb as B,gb as C,k as j,ma as p,mb as G,na as y,oa as V,ob as w,qb as M,va as A,xa as k,za as $}from"./chunk-ZWUSPUI7.js";import{a as d}from"./chunk-TQPZRHFO.js";function _t(a,r){if(a&1){let t=K();v(0,"div",1)(1,"button",2),x("click",function(){F(t);let n=S();return N(n.action())}),w(2),f()()}if(a&2){let t=S();p(2),M(" ",t.data.action," ")}}var bt=["label"];function kt(a,r){}var vt=Math.pow(2,31)-1,_=class{_overlayRef;instance;containerInstance;_afterDismissed=new l;_afterOpened=new l;_onAction=new l;_durationTimeoutId;_dismissedByAction=!1;constructor(r,t){this._overlayRef=t,this.containerInstance=r,r._onExit.subscribe(()=>this._finishDismiss())}dismiss(){this._afterDismissed.closed||this.containerInstance.exit(),clearTimeout(this._durationTimeoutId)}dismissWithAction(){this._onAction.closed||(this._dismissedByAction=!0,this._onAction.next(),this._onAction.complete(),this.dismiss()),clearTimeout(this._durationTimeoutId)}closeWithAction(){this.dismissWithAction()}_dismissAfter(r){this._durationTimeoutId=setTimeout(()=>this.dismiss(),Math.min(r,vt))}_open(){this._afterOpened.closed||(this._afterOpened.next(),this._afterOpened.complete())}_finishDismiss(){this._overlayRef.dispose(),this._onAction.closed||this._onAction.complete(),this._afterDismissed.next({dismissedByAction:this._dismissedByAction}),this._afterDismissed.complete(),this._dismissedByAction=!1}afterDismissed(){return this._afterDismissed}afterOpened(){return this.containerInstance._onEnter}onAction(){return this._onAction}},dt=new g("MatSnackBarData"),m=class{politeness="polite";announcementMessage="";viewContainerRef;duration=0;panelClass;direction;data=null;horizontalPosition="center";verticalPosition="bottom"},gt=(()=>{class a{static \u0275fac=function(e){return new(e||a)};static \u0275dir=k({type:a,selectors:[["","matSnackBarLabel",""]],hostAttrs:[1,"mat-mdc-snack-bar-label","mdc-snackbar__label"]})}return a})(),yt=(()=>{class a{static \u0275fac=function(e){return new(e||a)};static \u0275dir=k({type:a,selectors:[["","matSnackBarActions",""]],hostAttrs:[1,"mat-mdc-snack-bar-actions","mdc-snackbar__actions"]})}return a})(),At=(()=>{class a{static \u0275fac=function(e){return new(e||a)};static \u0275dir=k({type:a,selectors:[["","matSnackBarAction",""]],hostAttrs:[1,"mat-mdc-snack-bar-action","mdc-snackbar__action"]})}return a})(),xt=(()=>{class a{snackBarRef=o(_);data=o(dt);constructor(){}action(){this.snackBarRef.dismissWithAction()}get hasAction(){return!!this.data.action}static \u0275fac=function(e){return new(e||a)};static \u0275cmp=A({type:a,selectors:[["simple-snack-bar"]],hostAttrs:[1,"mat-mdc-simple-snack-bar"],exportAs:["matSnackBar"],decls:3,vars:2,consts:[["matSnackBarLabel",""],["matSnackBarActions",""],["matButton","","matSnackBarAction","",3,"click"]],template:function(e,n){e&1&&(v(0,"div",0),w(1),f(),Q(2,_t,3,1,"div",1)),e&2&&(p(),M(" ",n.data.message,`
`),p(),U(n.hasAction?2:-1))},dependencies:[it,gt,yt,At],styles:[`.mat-mdc-simple-snack-bar {
  display: flex;
}
.mat-mdc-simple-snack-bar .mat-mdc-snack-bar-label {
  max-height: 50vh;
  overflow: auto;
}
`],encapsulation:2,changeDetection:0})}return a})(),I="_mat-snack-bar-enter",O="_mat-snack-bar-exit",St=(()=>{class a extends rt{_ngZone=o(z);_elementRef=o(q);_changeDetectorRef=o(J);_platform=o(Y);_animationsDisabled=D();snackBarConfig=o(m);_document=o(L);_trackedModals=new Set;_enterFallback;_exitFallback;_injector=o(h);_announceDelay=150;_announceTimeoutId;_destroyed=!1;_portalOutlet;_onAnnounce=new l;_onExit=new l;_onEnter=new l;_animationState="void";_live;_label;_role;_liveElementId=o(nt).getId("mat-snack-bar-container-live-");constructor(){super();let t=this.snackBarConfig;t.politeness==="assertive"&&!t.announcementMessage?this._live="assertive":t.politeness==="off"?this._live="off":this._live="polite",this._platform.FIREFOX&&(this._live==="polite"&&(this._role="status"),this._live==="assertive"&&(this._role="alert"))}attachComponentPortal(t){this._assertNotAttached();let e=this._portalOutlet.attachComponentPortal(t);return this._afterPortalAttached(),e}attachTemplatePortal(t){this._assertNotAttached();let e=this._portalOutlet.attachTemplatePortal(t);return this._afterPortalAttached(),e}attachDomPortal=t=>{this._assertNotAttached();let e=this._portalOutlet.attachDomPortal(t);return this._afterPortalAttached(),e};onAnimationEnd(t){t===O?this._completeExit():t===I&&(clearTimeout(this._enterFallback),this._ngZone.run(()=>{this._onEnter.next(),this._onEnter.complete()}))}enter(){this._destroyed||(this._animationState="visible",this._changeDetectorRef.markForCheck(),this._changeDetectorRef.detectChanges(),this._screenReaderAnnounce(),this._animationsDisabled?y(()=>{this._ngZone.run(()=>queueMicrotask(()=>this.onAnimationEnd(I)))},{injector:this._injector}):(clearTimeout(this._enterFallback),this._enterFallback=setTimeout(()=>{this._elementRef.nativeElement.classList.add("mat-snack-bar-fallback-visible"),this.onAnimationEnd(I)},200)))}exit(){return this._destroyed?j(void 0):(this._ngZone.run(()=>{this._animationState="hidden",this._changeDetectorRef.markForCheck(),this._elementRef.nativeElement.setAttribute("mat-exit",""),clearTimeout(this._announceTimeoutId),this._animationsDisabled?y(()=>{this._ngZone.run(()=>queueMicrotask(()=>this.onAnimationEnd(O)))},{injector:this._injector}):(clearTimeout(this._exitFallback),this._exitFallback=setTimeout(()=>this.onAnimationEnd(O),200))}),this._onExit)}ngOnDestroy(){this._destroyed=!0,this._clearFromModals(),this._completeExit()}_completeExit(){clearTimeout(this._exitFallback),queueMicrotask(()=>{this._onExit.next(),this._onExit.complete()})}_afterPortalAttached(){let t=this._elementRef.nativeElement,e=this.snackBarConfig.panelClass;e&&(Array.isArray(e)?e.forEach(s=>t.classList.add(s)):t.classList.add(e)),this._exposeToModals();let n=this._label.nativeElement,i="mdc-snackbar__label";n.classList.toggle(i,!n.querySelector(`.${i}`))}_exposeToModals(){let t=this._liveElementId,e=this._document.querySelectorAll('body > .cdk-overlay-container [aria-modal="true"]');for(let n=0;n<e.length;n++){let i=e[n],s=i.getAttribute("aria-owns");this._trackedModals.add(i),s?s.indexOf(t)===-1&&i.setAttribute("aria-owns",s+" "+t):i.setAttribute("aria-owns",t)}}_clearFromModals(){this._trackedModals.forEach(t=>{let e=t.getAttribute("aria-owns");if(e){let n=e.replace(this._liveElementId,"").trim();n.length>0?t.setAttribute("aria-owns",n):t.removeAttribute("aria-owns")}}),this._trackedModals.clear()}_assertNotAttached(){this._portalOutlet.hasAttached()}_screenReaderAnnounce(){this._announceTimeoutId||this._ngZone.runOutsideAngular(()=>{this._announceTimeoutId=setTimeout(()=>{if(this._destroyed)return;let t=this._elementRef.nativeElement,e=t.querySelector("[aria-hidden]"),n=t.querySelector("[aria-live]");if(e&&n){let i=null;this._platform.isBrowser&&document.activeElement instanceof HTMLElement&&e.contains(document.activeElement)&&(i=document.activeElement),e.removeAttribute("aria-hidden"),n.appendChild(e),i?.focus(),this._onAnnounce.next(),this._onAnnounce.complete()}},this._announceDelay)})}static \u0275fac=function(e){return new(e||a)};static \u0275cmp=A({type:a,selectors:[["mat-snack-bar-container"]],viewQuery:function(e,n){if(e&1&&X(R,7)(bt,7),e&2){let i;B(i=C())&&(n._portalOutlet=i.first),B(i=C())&&(n._label=i.first)}},hostAttrs:[1,"mdc-snackbar","mat-mdc-snack-bar-container"],hostVars:6,hostBindings:function(e,n){e&1&&x("animationend",function(s){return n.onAnimationEnd(s.animationName)})("animationcancel",function(s){return n.onAnimationEnd(s.animationName)}),e&2&&G("mat-snack-bar-container-enter",n._animationState==="visible")("mat-snack-bar-container-exit",n._animationState==="hidden")("mat-snack-bar-container-animations-enabled",!n._animationsDisabled)},features:[$],decls:6,vars:3,consts:[["label",""],[1,"mdc-snackbar__surface","mat-mdc-snackbar-surface"],[1,"mat-mdc-snack-bar-label"],["aria-hidden","true"],["cdkPortalOutlet",""]],template:function(e,n){e&1&&(v(0,"div",1)(1,"div",2,0)(3,"div",3),H(4,kt,0,0,"ng-template",4),f(),W(5,"div"),f()()),e&2&&(p(5),Z("aria-live",n._live)("role",n._role)("id",n._liveElementId))},dependencies:[R],styles:[`@keyframes _mat-snack-bar-enter {
  from {
    transform: scale(0.8);
    opacity: 0;
  }
  to {
    transform: scale(1);
    opacity: 1;
  }
}
@keyframes _mat-snack-bar-exit {
  from {
    opacity: 1;
  }
  to {
    opacity: 0;
  }
}
.mat-mdc-snack-bar-container {
  display: flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  -webkit-tap-highlight-color: rgba(0, 0, 0, 0);
  margin: 8px;
}
.mat-mdc-snack-bar-handset .mat-mdc-snack-bar-container {
  width: 100vw;
}

.mat-snack-bar-container-animations-enabled {
  opacity: 0;
}
.mat-snack-bar-container-animations-enabled.mat-snack-bar-fallback-visible {
  opacity: 1;
}
.mat-snack-bar-container-animations-enabled.mat-snack-bar-container-enter {
  animation: _mat-snack-bar-enter 150ms cubic-bezier(0, 0, 0.2, 1) forwards;
}
.mat-snack-bar-container-animations-enabled.mat-snack-bar-container-exit {
  animation: _mat-snack-bar-exit 75ms cubic-bezier(0.4, 0, 1, 1) forwards;
}

.mat-mdc-snackbar-surface {
  box-shadow: 0px 3px 5px -1px rgba(0, 0, 0, 0.2), 0px 6px 10px 0px rgba(0, 0, 0, 0.14), 0px 1px 18px 0px rgba(0, 0, 0, 0.12);
  display: flex;
  align-items: center;
  justify-content: flex-start;
  box-sizing: border-box;
  padding-left: 0;
  padding-right: 8px;
}
[dir=rtl] .mat-mdc-snackbar-surface {
  padding-right: 0;
  padding-left: 8px;
}
.mat-mdc-snack-bar-container .mat-mdc-snackbar-surface {
  min-width: 344px;
  max-width: 672px;
}
.mat-mdc-snack-bar-handset .mat-mdc-snackbar-surface {
  width: 100%;
  min-width: 0;
}
@media (forced-colors: active) {
  .mat-mdc-snackbar-surface {
    outline: solid 1px;
  }
}
.mat-mdc-snack-bar-container .mat-mdc-snackbar-surface {
  color: var(--mat-snack-bar-supporting-text-color, var(--mat-sys-inverse-on-surface));
  border-radius: var(--mat-snack-bar-container-shape, var(--mat-sys-corner-extra-small));
  background-color: var(--mat-snack-bar-container-color, var(--mat-sys-inverse-surface));
}

.mdc-snackbar__label {
  width: 100%;
  flex-grow: 1;
  box-sizing: border-box;
  margin: 0;
  padding: 14px 8px 14px 16px;
}
[dir=rtl] .mdc-snackbar__label {
  padding-left: 8px;
  padding-right: 16px;
}
.mat-mdc-snack-bar-container .mdc-snackbar__label {
  font-family: var(--mat-snack-bar-supporting-text-font, var(--mat-sys-body-medium-font));
  font-size: var(--mat-snack-bar-supporting-text-size, var(--mat-sys-body-medium-size));
  font-weight: var(--mat-snack-bar-supporting-text-weight, var(--mat-sys-body-medium-weight));
  line-height: var(--mat-snack-bar-supporting-text-line-height, var(--mat-sys-body-medium-line-height));
}

.mat-mdc-snack-bar-actions {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  box-sizing: border-box;
}

.mat-mdc-snack-bar-handset,
.mat-mdc-snack-bar-container,
.mat-mdc-snack-bar-label {
  flex: 1 1 auto;
}

.mat-mdc-snack-bar-container .mat-mdc-button.mat-mdc-snack-bar-action:not(:disabled).mat-unthemed {
  color: var(--mat-snack-bar-button-color, var(--mat-sys-inverse-primary));
}
.mat-mdc-snack-bar-container .mat-mdc-button.mat-mdc-snack-bar-action:not(:disabled) {
  --mat-button-text-state-layer-color: currentColor;
  --mat-button-text-ripple-color: currentColor;
}
.mat-mdc-snack-bar-container .mat-mdc-button.mat-mdc-snack-bar-action:not(:disabled) .mat-ripple-element {
  opacity: 0.1;
}
`],encapsulation:2})}return a})(),Bt=new g("mat-snack-bar-default-options",{providedIn:"root",factory:()=>new m}),mt=(()=>{class a{_live=o(et);_injector=o(h);_breakpointObserver=o(tt);_parentSnackBar=o(a,{optional:!0,skipSelf:!0});_defaultConfig=o(Bt);_animationsDisabled=D();_snackBarRefAtThisLevel=null;simpleSnackBarComponent=xt;snackBarContainerComponent=St;handsetCssClass="mat-mdc-snack-bar-handset";get _openedSnackBarRef(){let t=this._parentSnackBar;return t?t._openedSnackBarRef:this._snackBarRefAtThisLevel}set _openedSnackBarRef(t){this._parentSnackBar?this._parentSnackBar._openedSnackBarRef=t:this._snackBarRefAtThisLevel=t}constructor(){}openFromComponent(t,e){return this._attach(t,e)}openFromTemplate(t,e){return this._attach(t,e)}open(t,e="",n){let i=d(d({},this._defaultConfig),n);return i.data={message:t,action:e},i.announcementMessage===t&&(i.announcementMessage=void 0),this.openFromComponent(this.simpleSnackBarComponent,i)}dismiss(){this._openedSnackBarRef&&this._openedSnackBarRef.dismiss()}ngOnDestroy(){this._snackBarRefAtThisLevel&&this._snackBarRefAtThisLevel.dismiss()}_attachSnackBarContainer(t,e){let n=e&&e.viewContainerRef&&e.viewContainerRef.injector,i=h.create({parent:n||this._injector,providers:[{provide:m,useValue:e}]}),s=new E(this.snackBarContainerComponent,e.viewContainerRef,i),c=t.attach(s);return c.instance.snackBarConfig=e,c.instance}_attach(t,e){let n=d(d(d({},new m),this._defaultConfig),e),i=this._createOverlay(n),s=this._attachSnackBarContainer(i,n),c=new _(s,i);if(t instanceof V){let u=new st(t,null,{$implicit:n.data,snackBarRef:c});c.instance=s.attachTemplatePortal(u)}else{let u=this._createInjector(n,c),ht=new E(t,void 0,u),pt=s.attachComponentPortal(ht);c.instance=pt.instance}return this._breakpointObserver.observe(at.HandsetPortrait).pipe(P(i.detachments())).subscribe(u=>{i.overlayElement.classList.toggle(this.handsetCssClass,u.matches)}),n.announcementMessage&&s._onAnnounce.subscribe(()=>{this._live.announce(n.announcementMessage,n.politeness)}),this._animateSnackBar(c,n),this._openedSnackBarRef=c,this._openedSnackBarRef}_animateSnackBar(t,e){t.afterDismissed().subscribe(()=>{this._openedSnackBarRef==t&&(this._openedSnackBarRef=null),e.announcementMessage&&this._live.clear()}),e.duration&&e.duration>0&&t.afterOpened().subscribe(()=>t._dismissAfter(e.duration)),this._openedSnackBarRef?(this._openedSnackBarRef.afterDismissed().subscribe(()=>{t.containerInstance.enter()}),this._openedSnackBarRef.dismiss()):t.containerInstance.enter()}_createOverlay(t){let e=new ot;e.direction=t.direction;let n=ct(this._injector),i=t.direction==="rtl",s=t.horizontalPosition==="left"||t.horizontalPosition==="start"&&!i||t.horizontalPosition==="end"&&i,c=!s&&t.horizontalPosition!=="center";return s?n.left("0"):c?n.right("0"):n.centerHorizontally(),t.verticalPosition==="top"?n.top("0"):n.bottom("0"),e.positionStrategy=n,e.disableAnimations=this._animationsDisabled,lt(this._injector,e)}_createInjector(t,e){let n=t&&t.viewContainerRef&&t.viewContainerRef.injector;return h.create({parent:n||this._injector,providers:[{provide:_,useValue:e},{provide:dt,useValue:t.data}]})}static \u0275fac=function(e){return new(e||a)};static \u0275prov=b({token:a,factory:a.\u0275fac,providedIn:"root"})}return a})();var ut=class a{snack=o(mt);success(r){this.snack.open(r,"OK",{duration:3500,panelClass:"snack-success"})}error(r,t="Something went wrong."){let e=r instanceof T?r:T.from(r),n=e.requestId?` (ref ${e.requestId.slice(0,8)})`:"",i=Ct(e);this.snack.open(`${e.message||t}${i}${n}`,"Dismiss",{duration:i?12e3:7e3,panelClass:"snack-error"})}static \u0275fac=function(t){return new(t||a)};static \u0275prov=b({token:a,factory:a.\u0275fac,providedIn:"root"})};function Ct(a){let r=a.fieldErrors.filter(n=>n.message);if(!r.length)return"";let t=n=>(n.split(".").pop()||n).replace(/_/g," ").replace(/^./,i=>i.toUpperCase());return` \u2014 ${r.slice(0,3).map(n=>n.field?`${t(n.field)}: ${n.message}`:n.message).join("; ")}${r.length>3?` (+${r.length-3} more)`:""}`}export{ut as a};
