import{a as ht}from"./chunk-HEFDUKE4.js";import{a as mt}from"./chunk-MDPEJPYK.js";import{A as $,d as le,e as it,f as nt,h as F,i as P,k as at,p as Y,r as ot,s as rt,t as st,v as Z,x as lt}from"./chunk-CR2I6BNW.js";import{c as dt,d as ct}from"./chunk-HD3XYCDK.js";import{A as Ze,B as $e,D as Ke,H as Xe,I as Je,b as Ve,d as M,f as Ge,g as He,h as ze,j as re,l as We,r as qe,s as Qe,x as Ue,z as Ye}from"./chunk-SW7XBUG3.js";import{I as se,P as et,Q as tt,c as Q,e as Fe,f as ae,h as Pe,o as Le,p as Be,r as Ne,s as U,v as R}from"./chunk-MVNFUC75.js";import{$ as ve,Aa as W,H as N,Ha as T,Ia as O,Ja as k,O as j,Oa as te,P as V,Pa as d,Q as _,Qa as c,R as r,Ra as ie,Sb as Me,T as ye,U as be,X as p,Y as De,Ya as ke,Za as ne,_ as G,_a as S,ab as I,ba as Ce,d as f,da as Ae,ea as H,eb as Se,f as ee,fa as w,fb as Ie,gb as Ee,ma as m,mb as E,na as xe,oa as we,ob as h,pb as q,pc as oe,qa as Te,qb as Re,qc as je,r as B,u as _e,v as x,va as v,wa as z,xa as C,ya as Oe,z as D,za as A}from"./chunk-ZWUSPUI7.js";import{a as g,b as fe}from"./chunk-TQPZRHFO.js";function kt(i,a){}var y=class{viewContainerRef;injector;id;role="dialog";panelClass="";hasBackdrop=!0;backdropClass="";disableClose=!1;closePredicate;width="";height="";minWidth;minHeight;maxWidth;maxHeight;positionStrategy;data=null;direction;ariaDescribedBy=null;ariaLabelledBy=null;ariaLabel=null;ariaModal=!1;autoFocus="first-tabbable";restoreFocus=!0;scrollStrategy;closeOnNavigation=!0;closeOnDestroy=!0;closeOnOverlayDetachments=!0;disableAnimations=!1;providers;container;templateContext};var ce=(()=>{class i extends nt{_elementRef=r(w);_focusTrapFactory=r(Be);_config;_interactivityChecker=r(Le);_ngZone=r(ve);_focusMonitor=r(Pe);_renderer=r(Te);_changeDetectorRef=r(Me);_injector=r(p);_platform=r(Fe);_document=r(De);_portalOutlet;_focusTrapped=new f;_focusTrap=null;_elementFocusedBeforeDialogWasOpened=null;_closeInteractionType=null;_ariaLabelledByQueue=[];_isDestroyed=!1;constructor(){super(),this._config=r(y,{optional:!0})||new y,this._config.ariaLabelledBy&&this._ariaLabelledByQueue.push(this._config.ariaLabelledBy)}_addAriaLabelledBy(e){this._ariaLabelledByQueue.push(e),this._changeDetectorRef.markForCheck()}_removeAriaLabelledBy(e){let t=this._ariaLabelledByQueue.indexOf(e);t>-1&&(this._ariaLabelledByQueue.splice(t,1),this._changeDetectorRef.markForCheck())}_contentAttached(){this._initializeFocusTrap(),this._captureInitialFocus()}_captureInitialFocus(){this._trapFocus()}ngOnDestroy(){this._focusTrapped.complete(),this._isDestroyed=!0,this._restoreFocus()}attachComponentPortal(e){this._portalOutlet.hasAttached();let t=this._portalOutlet.attachComponentPortal(e);return this._contentAttached(),t}attachTemplatePortal(e){this._portalOutlet.hasAttached();let t=this._portalOutlet.attachTemplatePortal(e);return this._contentAttached(),t}attachDomPortal=e=>{this._portalOutlet.hasAttached();let t=this._portalOutlet.attachDomPortal(e);return this._contentAttached(),t};_recaptureFocus(){this._containsFocus()||this._trapFocus()}_forceFocus(e,t){this._interactivityChecker.isFocusable(e)||(e.tabIndex=-1,this._ngZone.runOutsideAngular(()=>{let n=()=>{o(),l(),e.removeAttribute("tabindex")},o=this._renderer.listen(e,"blur",n),l=this._renderer.listen(e,"mousedown",n)})),e.focus(t)}_focusByCssSelector(e,t){let n=this._elementRef.nativeElement.querySelector(e);n&&this._forceFocus(n,t)}_trapFocus(e){this._isDestroyed||xe(()=>{let t=this._elementRef.nativeElement;switch(this._config.autoFocus){case!1:case"dialog":this._containsFocus()||t.focus(e);break;case!0:case"first-tabbable":this._focusTrap?.focusInitialElement(e)||this._focusDialogContainer(e);break;case"first-heading":this._focusByCssSelector('h1, h2, h3, h4, h5, h6, [role="heading"]',e);break;default:this._focusByCssSelector(this._config.autoFocus,e);break}this._focusTrapped.next()},{injector:this._injector})}_restoreFocus(){let e=this._config.restoreFocus,t=null;if(typeof e=="string"?t=this._document.querySelector(e):typeof e=="boolean"?t=e?this._elementFocusedBeforeDialogWasOpened:null:e&&(t=e),this._config.restoreFocus&&t&&typeof t.focus=="function"){let n=Q(),o=this._elementRef.nativeElement;(!n||n===this._document.body||n===o||o.contains(n))&&(this._focusMonitor?(this._focusMonitor.focusVia(t,this._closeInteractionType),this._closeInteractionType=null):t.focus())}this._focusTrap&&this._focusTrap.destroy()}_focusDialogContainer(e){this._elementRef.nativeElement.focus?.(e)}_containsFocus(){let e=this._elementRef.nativeElement,t=Q();return e===t||e.contains(t)}_initializeFocusTrap(){this._platform.isBrowser&&(this._focusTrap=this._focusTrapFactory.create(this._elementRef.nativeElement),this._document&&(this._elementFocusedBeforeDialogWasOpened=Q()))}static \u0275fac=function(t){return new(t||i)};static \u0275cmp=v({type:i,selectors:[["cdk-dialog-container"]],viewQuery:function(t,n){if(t&1&&Se(F,7),t&2){let o;Ie(o=Ee())&&(n._portalOutlet=o.first)}},hostAttrs:["tabindex","-1",1,"cdk-dialog-container"],hostVars:6,hostBindings:function(t,n){t&2&&T("id",n._config.id||null)("role",n._config.role)("aria-modal",n._config.ariaModal)("aria-labelledby",n._config.ariaLabel?null:n._ariaLabelledByQueue[0])("aria-label",n._config.ariaLabel)("aria-describedby",n._config.ariaDescribedBy||null)},features:[A],decls:1,vars:0,consts:[["cdkPortalOutlet",""]],template:function(t,n){t&1&&W(0,kt,0,0,"ng-template",0)},dependencies:[F],styles:[`.cdk-dialog-container {
  display: block;
  width: 100%;
  height: 100%;
  min-height: inherit;
  max-height: inherit;
}
`],encapsulation:2})}return i})(),L=class{overlayRef;config;componentInstance=null;componentRef=null;containerInstance;disableClose;closed=new f;backdropClick;keydownEvents;outsidePointerEvents;id;_detachSubscription;constructor(a,e){this.overlayRef=a,this.config=e,this.disableClose=e.disableClose,this.backdropClick=a.backdropClick(),this.keydownEvents=a.keydownEvents(),this.outsidePointerEvents=a.outsidePointerEvents(),this.id=e.id,this.keydownEvents.subscribe(t=>{t.keyCode===27&&!this.disableClose&&!U(t)&&(t.preventDefault(),this.close(void 0,{focusOrigin:"keyboard"}))}),this.backdropClick.subscribe(()=>{!this.disableClose&&this._canClose()?this.close(void 0,{focusOrigin:"mouse"}):this.containerInstance._recaptureFocus?.()}),this._detachSubscription=a.detachments().subscribe(()=>{e.closeOnOverlayDetachments!==!1&&this.close()})}close(a,e){if(this._canClose(a)){let t=this.closed;this.containerInstance._closeInteractionType=e?.focusOrigin||"program",this._detachSubscription.unsubscribe(),this.overlayRef.dispose(),t.next(a),t.complete(),this.componentInstance=this.containerInstance=null}}updatePosition(){return this.overlayRef.updatePosition(),this}updateSize(a="",e=""){return this.overlayRef.updateSize({width:a,height:e}),this}addPanelClass(a){return this.overlayRef.addPanelClass(a),this}removePanelClass(a){return this.overlayRef.removePanelClass(a),this}_canClose(a){let e=this.config;return!!this.containerInstance&&(!e.closePredicate||e.closePredicate(a,e,this.componentInstance))}},St=new _("DialogScrollStrategy",{providedIn:"root",factory:()=>{let i=r(p);return()=>Y(i)}}),It=new _("DialogData"),Et=new _("DefaultDialogConfig");function Rt(i){let a=Ce(i),e=new G;return{valueSignal:a,get value(){return a()},change:e,ngOnDestroy(){e.complete()}}}var me=(()=>{class i{_injector=r(p);_defaultOptions=r(Et,{optional:!0});_parentDialog=r(i,{optional:!0,skipSelf:!0});_overlayContainer=r(rt);_idGenerator=r(R);_openDialogsAtThisLevel=[];_afterAllClosedAtThisLevel=new f;_afterOpenedAtThisLevel=new f;_ariaHiddenElements=new Map;_scrollStrategy=r(St);get openDialogs(){return this._parentDialog?this._parentDialog.openDialogs:this._openDialogsAtThisLevel}get afterOpened(){return this._parentDialog?this._parentDialog.afterOpened:this._afterOpenedAtThisLevel}afterAllClosed=B(()=>this.openDialogs.length?this._getAfterAllClosed():this._getAfterAllClosed().pipe(N(void 0)));constructor(){}open(e,t){let n=this._defaultOptions||new y;t=g(g({},n),t),t.id=t.id||this._idGenerator.getId("cdk-dialog-"),t.id&&this.getDialogById(t.id);let o=this._getOverlayConfig(t),l=lt(this._injector,o),s=new L(l,t),u=this._attachContainer(l,s,t);if(s.containerInstance=u,!this.openDialogs.length){let J=this._overlayContainer.getContainerElement();u._focusTrapped?u._focusTrapped.pipe(D(1)).subscribe(()=>{this._hideNonDialogContentFromAssistiveTechnology(J)}):this._hideNonDialogContentFromAssistiveTechnology(J)}return this._attachDialogContent(e,s,u,t),this.openDialogs.push(s),s.closed.subscribe(()=>this._removeOpenDialog(s,!0)),this.afterOpened.next(s),s}closeAll(){de(this.openDialogs,e=>e.close())}getDialogById(e){return this.openDialogs.find(t=>t.id===e)}ngOnDestroy(){de(this._openDialogsAtThisLevel,e=>{e.config.closeOnDestroy===!1&&this._removeOpenDialog(e,!1)}),de(this._openDialogsAtThisLevel,e=>e.close()),this._afterAllClosedAtThisLevel.complete(),this._afterOpenedAtThisLevel.complete(),this._openDialogsAtThisLevel=[]}_getOverlayConfig(e){let t=new ot({positionStrategy:e.positionStrategy||Z().centerHorizontally().centerVertically(),scrollStrategy:e.scrollStrategy||this._scrollStrategy(),panelClass:e.panelClass,hasBackdrop:e.hasBackdrop,direction:e.direction,minWidth:e.minWidth,minHeight:e.minHeight,maxWidth:e.maxWidth,maxHeight:e.maxHeight,width:e.width,height:e.height,disposeOnNavigation:e.closeOnNavigation,disableAnimations:e.disableAnimations});return e.backdropClass&&(t.backdropClass=e.backdropClass),t}_attachContainer(e,t,n){let o=n.injector||n.viewContainerRef?.injector,l=[{provide:y,useValue:n},{provide:L,useValue:t},{provide:st,useValue:e}],s;n.container?typeof n.container=="function"?s=n.container:(s=n.container.type,l.push(...n.container.providers(n))):s=ce;let u=new le(s,n.viewContainerRef,p.create({parent:o||this._injector,providers:l}));return e.attach(u).instance}_attachDialogContent(e,t,n,o){if(e instanceof we){let l=this._createInjector(o,t,n,void 0),s={$implicit:o.data,dialogRef:t};o.templateContext&&(s=g(g({},s),typeof o.templateContext=="function"?o.templateContext():o.templateContext)),n.attachTemplatePortal(new it(e,null,s,l))}else{let l=this._createInjector(o,t,n,this._injector),s=n.attachComponentPortal(new le(e,o.viewContainerRef,l));t.componentRef=s,t.componentInstance=s.instance}}_createInjector(e,t,n,o){let l=e.injector||e.viewContainerRef?.injector,s=[{provide:It,useValue:e.data},{provide:L,useValue:t}];return e.providers&&(typeof e.providers=="function"?s.push(...e.providers(t,e,n)):s.push(...e.providers)),e.direction&&(!l||!l.get(oe,null,{optional:!0}))&&s.push({provide:oe,useValue:Rt(e.direction)}),p.create({parent:l||o,providers:s})}_removeOpenDialog(e,t){let n=this.openDialogs.indexOf(e);n>-1&&(this.openDialogs.splice(n,1),this.openDialogs.length||(this._ariaHiddenElements.forEach((o,l)=>{o?l.setAttribute("aria-hidden",o):l.removeAttribute("aria-hidden")}),this._ariaHiddenElements.clear(),t&&this._getAfterAllClosed().next()))}_hideNonDialogContentFromAssistiveTechnology(e){if(e.parentElement){let t=e.parentElement.children;for(let n=t.length-1;n>-1;n--){let o=t[n];o!==e&&o.nodeName!=="SCRIPT"&&o.nodeName!=="STYLE"&&!o.hasAttribute("aria-live")&&!o.hasAttribute("popover")&&(this._ariaHiddenElements.set(o,o.getAttribute("aria-hidden")),o.setAttribute("aria-hidden","true"))}}}_getAfterAllClosed(){let e=this._parentDialog;return e?e._getAfterAllClosed():this._afterAllClosedAtThisLevel}static \u0275fac=function(t){return new(t||i)};static \u0275prov=j({token:i,factory:i.\u0275fac,providedIn:"root"})}return i})();function de(i,a){let e=i.length;for(;e--;)a(i[e])}var pt=(()=>{class i{static \u0275fac=function(t){return new(t||i)};static \u0275mod=z({type:i});static \u0275inj=V({providers:[me],imports:[$,P,Ne,P]})}return i})();function Mt(i,a){}var X=class{viewContainerRef;injector;id;role="dialog";panelClass="";hasBackdrop=!0;backdropClass="";disableClose=!1;closePredicate;width="";height="";minWidth;minHeight;maxWidth;maxHeight;position;data=null;direction;ariaDescribedBy=null;ariaLabelledBy=null;ariaLabel=null;ariaModal=!1;autoFocus="first-tabbable";restoreFocus=!0;delayFocusTrap=!0;scrollStrategy;closeOnNavigation=!0;enterAnimationDuration;exitAnimationDuration},he="mdc-dialog--open",ft="mdc-dialog--opening",_t="mdc-dialog--closing",Ft=150,Pt=75,Lt=(()=>{class i extends ce{_animationStateChanged=new G;_animationsEnabled=!se();_actionSectionCount=0;_hostElement=this._elementRef.nativeElement;_enterAnimationDuration=this._animationsEnabled?bt(this._config.enterAnimationDuration)??Ft:0;_exitAnimationDuration=this._animationsEnabled?bt(this._config.exitAnimationDuration)??Pt:0;_animationTimer=null;_contentAttached(){super._contentAttached(),this._startOpenAnimation()}_startOpenAnimation(){this._animationStateChanged.emit({state:"opening",totalTime:this._enterAnimationDuration}),this._animationsEnabled?(this._hostElement.style.setProperty(yt,`${this._enterAnimationDuration}ms`),this._requestAnimationFrame(()=>this._hostElement.classList.add(ft,he)),this._waitForAnimationToComplete(this._enterAnimationDuration,this._finishDialogOpen)):(this._hostElement.classList.add(he),Promise.resolve().then(()=>this._finishDialogOpen()))}_startExitAnimation(){this._animationStateChanged.emit({state:"closing",totalTime:this._exitAnimationDuration}),this._hostElement.classList.remove(he),this._animationsEnabled?(this._hostElement.style.setProperty(yt,`${this._exitAnimationDuration}ms`),this._requestAnimationFrame(()=>this._hostElement.classList.add(_t)),this._waitForAnimationToComplete(this._exitAnimationDuration,this._finishDialogClose)):Promise.resolve().then(()=>this._finishDialogClose())}_updateActionSectionCount(e){this._actionSectionCount+=e,this._changeDetectorRef.markForCheck()}_finishDialogOpen=()=>{this._clearAnimationClasses(),this._openAnimationDone(this._enterAnimationDuration)};_finishDialogClose=()=>{this._clearAnimationClasses(),this._animationStateChanged.emit({state:"closed",totalTime:this._exitAnimationDuration})};_clearAnimationClasses(){this._hostElement.classList.remove(ft,_t)}_waitForAnimationToComplete(e,t){this._animationTimer!==null&&clearTimeout(this._animationTimer),this._animationTimer=setTimeout(t,e)}_requestAnimationFrame(e){this._ngZone.runOutsideAngular(()=>{typeof requestAnimationFrame=="function"?requestAnimationFrame(e):e()})}_captureInitialFocus(){this._config.delayFocusTrap||this._trapFocus()}_openAnimationDone(e){this._config.delayFocusTrap&&this._trapFocus(),this._animationStateChanged.next({state:"opened",totalTime:e})}ngOnDestroy(){super.ngOnDestroy(),this._animationTimer!==null&&clearTimeout(this._animationTimer)}attachComponentPortal(e){let t=super.attachComponentPortal(e);return t.location.nativeElement.classList.add("mat-mdc-dialog-component-host"),t}static \u0275fac=(()=>{let e;return function(n){return(e||(e=H(i)))(n||i)}})();static \u0275cmp=v({type:i,selectors:[["mat-dialog-container"]],hostAttrs:["tabindex","-1",1,"mat-mdc-dialog-container","mdc-dialog"],hostVars:10,hostBindings:function(t,n){t&2&&(ne("id",n._config.id),T("aria-modal",n._config.ariaModal)("role",n._config.role)("aria-labelledby",n._config.ariaLabel?null:n._ariaLabelledByQueue[0])("aria-label",n._config.ariaLabel)("aria-describedby",n._config.ariaDescribedBy||null),E("_mat-animation-noopable",!n._animationsEnabled)("mat-mdc-dialog-container-with-actions",n._actionSectionCount>0))},features:[A],decls:3,vars:0,consts:[[1,"mat-mdc-dialog-inner-container","mdc-dialog__container"],[1,"mat-mdc-dialog-surface","mdc-dialog__surface"],["cdkPortalOutlet",""]],template:function(t,n){t&1&&(d(0,"div",0)(1,"div",1),W(2,Mt,0,0,"ng-template",2),c()())},dependencies:[F],styles:[`.mat-mdc-dialog-container {
  width: 100%;
  height: 100%;
  display: block;
  box-sizing: border-box;
  max-height: inherit;
  min-height: inherit;
  min-width: inherit;
  max-width: inherit;
  outline: 0;
}

.cdk-overlay-pane.mat-mdc-dialog-panel {
  max-width: var(--mat-dialog-container-max-width, 560px);
  min-width: var(--mat-dialog-container-min-width, 280px);
}
@media (max-width: 599px) {
  .cdk-overlay-pane.mat-mdc-dialog-panel {
    max-width: var(--mat-dialog-container-small-max-width, calc(100vw - 32px));
  }
}

.mat-mdc-dialog-inner-container {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-around;
  box-sizing: border-box;
  height: 100%;
  opacity: 0;
  transition: opacity linear var(--mat-dialog-transition-duration, 0ms);
  max-height: inherit;
  min-height: inherit;
  min-width: inherit;
  max-width: inherit;
}
.mdc-dialog--closing .mat-mdc-dialog-inner-container {
  transition: opacity 75ms linear;
  transform: none;
}
.mdc-dialog--open .mat-mdc-dialog-inner-container {
  opacity: 1;
}
._mat-animation-noopable .mat-mdc-dialog-inner-container {
  transition: none;
}

.mat-mdc-dialog-surface {
  display: flex;
  flex-direction: column;
  flex-grow: 0;
  flex-shrink: 0;
  box-sizing: border-box;
  width: 100%;
  height: 100%;
  position: relative;
  overflow-y: auto;
  outline: 0;
  transform: scale(0.8);
  transition: transform var(--mat-dialog-transition-duration, 0ms) cubic-bezier(0, 0, 0.2, 1);
  max-height: inherit;
  min-height: inherit;
  min-width: inherit;
  max-width: inherit;
  box-shadow: var(--mat-dialog-container-elevation-shadow, none);
  border-radius: var(--mat-dialog-container-shape, var(--mat-sys-corner-extra-large, 4px));
  background-color: var(--mat-dialog-container-color, var(--mat-sys-surface, white));
}
[dir=rtl] .mat-mdc-dialog-surface {
  text-align: right;
}
.mdc-dialog--open .mat-mdc-dialog-surface, .mdc-dialog--closing .mat-mdc-dialog-surface {
  transform: none;
}
._mat-animation-noopable .mat-mdc-dialog-surface {
  transition: none;
}
.mat-mdc-dialog-surface::before {
  position: absolute;
  box-sizing: border-box;
  width: 100%;
  height: 100%;
  top: 0;
  left: 0;
  border: 2px solid transparent;
  border-radius: inherit;
  content: "";
  pointer-events: none;
}

.mat-mdc-dialog-title {
  display: block;
  position: relative;
  flex-shrink: 0;
  box-sizing: border-box;
  margin: 0 0 1px;
  padding: var(--mat-dialog-headline-padding, 6px 24px 13px);
}
.mat-mdc-dialog-title::before {
  display: inline-block;
  width: 0;
  height: 40px;
  content: "";
  vertical-align: 0;
}
[dir=rtl] .mat-mdc-dialog-title {
  text-align: right;
}
.mat-mdc-dialog-container .mat-mdc-dialog-title {
  color: var(--mat-dialog-subhead-color, var(--mat-sys-on-surface, rgba(0, 0, 0, 0.87)));
  font-family: var(--mat-dialog-subhead-font, var(--mat-sys-headline-small-font, inherit));
  line-height: var(--mat-dialog-subhead-line-height, var(--mat-sys-headline-small-line-height, 1.5rem));
  font-size: var(--mat-dialog-subhead-size, var(--mat-sys-headline-small-size, 1rem));
  font-weight: var(--mat-dialog-subhead-weight, var(--mat-sys-headline-small-weight, 400));
  letter-spacing: var(--mat-dialog-subhead-tracking, var(--mat-sys-headline-small-tracking, 0.03125em));
}

.mat-mdc-dialog-content {
  display: block;
  flex-grow: 1;
  box-sizing: border-box;
  margin: 0;
  overflow: auto;
  max-height: 65vh;
}
.mat-mdc-dialog-content > :first-child {
  margin-top: 0;
}
.mat-mdc-dialog-content > :last-child {
  margin-bottom: 0;
}
.mat-mdc-dialog-container .mat-mdc-dialog-content {
  color: var(--mat-dialog-supporting-text-color, var(--mat-sys-on-surface-variant, rgba(0, 0, 0, 0.6)));
  font-family: var(--mat-dialog-supporting-text-font, var(--mat-sys-body-medium-font, inherit));
  line-height: var(--mat-dialog-supporting-text-line-height, var(--mat-sys-body-medium-line-height, 1.5rem));
  font-size: var(--mat-dialog-supporting-text-size, var(--mat-sys-body-medium-size, 1rem));
  font-weight: var(--mat-dialog-supporting-text-weight, var(--mat-sys-body-medium-weight, 400));
  letter-spacing: var(--mat-dialog-supporting-text-tracking, var(--mat-sys-body-medium-tracking, 0.03125em));
}
.mat-mdc-dialog-container .mat-mdc-dialog-content {
  padding: var(--mat-dialog-content-padding, 20px 24px);
}
.mat-mdc-dialog-container-with-actions .mat-mdc-dialog-content {
  padding: var(--mat-dialog-with-actions-content-padding, 20px 24px 0);
}
.mat-mdc-dialog-container .mat-mdc-dialog-title + .mat-mdc-dialog-content {
  padding-top: 0;
}

.mat-mdc-dialog-actions {
  display: flex;
  position: relative;
  flex-shrink: 0;
  flex-wrap: wrap;
  align-items: center;
  box-sizing: border-box;
  min-height: 52px;
  margin: 0;
  border-top: 1px solid transparent;
  padding: var(--mat-dialog-actions-padding, 16px 24px);
  justify-content: var(--mat-dialog-actions-alignment, flex-end);
}
@media (forced-colors: active) {
  .mat-mdc-dialog-actions {
    border-top-color: CanvasText;
  }
}
.mat-mdc-dialog-actions.mat-mdc-dialog-actions-align-start, .mat-mdc-dialog-actions[align=start] {
  justify-content: start;
}
.mat-mdc-dialog-actions.mat-mdc-dialog-actions-align-center, .mat-mdc-dialog-actions[align=center] {
  justify-content: center;
}
.mat-mdc-dialog-actions.mat-mdc-dialog-actions-align-end, .mat-mdc-dialog-actions[align=end] {
  justify-content: flex-end;
}
.mat-mdc-dialog-actions .mat-button-base + .mat-button-base,
.mat-mdc-dialog-actions .mat-mdc-button-base + .mat-mdc-button-base {
  margin-left: 8px;
}
[dir=rtl] .mat-mdc-dialog-actions .mat-button-base + .mat-button-base,
[dir=rtl] .mat-mdc-dialog-actions .mat-mdc-button-base + .mat-mdc-button-base {
  margin-left: 0;
  margin-right: 8px;
}

.mat-mdc-dialog-component-host {
  display: contents;
}
`],encapsulation:2})}return i})(),yt="--mat-dialog-transition-duration";function bt(i){return i==null?null:typeof i=="number"?i:i.endsWith("ms")?ae(i.substring(0,i.length-2)):i.endsWith("s")?ae(i.substring(0,i.length-1))*1e3:i==="0"?0:null}var K=(function(i){return i[i.OPEN=0]="OPEN",i[i.CLOSING=1]="CLOSING",i[i.CLOSED=2]="CLOSED",i})(K||{}),b=class{_ref;_config;_containerInstance;componentInstance;componentRef=null;disableClose;id;_afterOpened=new ee(1);_beforeClosed=new ee(1);_result;_closeFallbackTimeout;_state=K.OPEN;_closeInteractionType;constructor(a,e,t){this._ref=a,this._config=e,this._containerInstance=t,this.disableClose=e.disableClose,this.id=a.id,a.addPanelClass("mat-mdc-dialog-panel"),t._animationStateChanged.pipe(x(n=>n.state==="opened"),D(1)).subscribe(()=>{this._afterOpened.next(),this._afterOpened.complete()}),t._animationStateChanged.pipe(x(n=>n.state==="closed"),D(1)).subscribe(()=>{clearTimeout(this._closeFallbackTimeout),this._finishDialogClose()}),a.overlayRef.detachments().subscribe(()=>{this._beforeClosed.next(this._result),this._beforeClosed.complete(),this._finishDialogClose()}),_e(this.backdropClick(),this.keydownEvents().pipe(x(n=>n.keyCode===27&&!this.disableClose&&!U(n)))).subscribe(n=>{this.disableClose||(n.preventDefault(),Dt(this,n.type==="keydown"?"keyboard":"mouse"))})}close(a){let e=this._config.closePredicate;e&&!e(a,this._config,this.componentInstance)||(this._result=a,this._containerInstance._animationStateChanged.pipe(x(t=>t.state==="closing"),D(1)).subscribe(t=>{this._beforeClosed.next(a),this._beforeClosed.complete(),this._ref.overlayRef.detachBackdrop(),this._closeFallbackTimeout=setTimeout(()=>this._finishDialogClose(),t.totalTime+100)}),this._state=K.CLOSING,this._containerInstance._startExitAnimation())}afterOpened(){return this._afterOpened}afterClosed(){return this._ref.closed}beforeClosed(){return this._beforeClosed}backdropClick(){return this._ref.backdropClick}keydownEvents(){return this._ref.keydownEvents}updatePosition(a){let e=this._ref.config.positionStrategy;return a&&(a.left||a.right)?a.left?e.left(a.left):e.right(a.right):e.centerHorizontally(),a&&(a.top||a.bottom)?a.top?e.top(a.top):e.bottom(a.bottom):e.centerVertically(),this._ref.updatePosition(),this}updateSize(a="",e=""){return this._ref.updateSize(a,e),this}addPanelClass(a){return this._ref.addPanelClass(a),this}removePanelClass(a){return this._ref.removePanelClass(a),this}getState(){return this._state}_finishDialogClose(){this._state=K.CLOSED,this._ref.close(this._result,{focusOrigin:this._closeInteractionType}),this.componentInstance=null}};function Dt(i,a,e){return i._closeInteractionType=a,i.close(e)}var ue=new _("MatMdcDialogData"),Bt=new _("mat-mdc-dialog-default-options"),Nt=new _("mat-mdc-dialog-scroll-strategy",{providedIn:"root",factory:()=>{let i=r(p);return()=>Y(i)}}),ge=(()=>{class i{_defaultOptions=r(Bt,{optional:!0});_scrollStrategy=r(Nt);_parentDialog=r(i,{optional:!0,skipSelf:!0});_idGenerator=r(R);_injector=r(p);_dialog=r(me);_animationsDisabled=se();_openDialogsAtThisLevel=[];_afterAllClosedAtThisLevel=new f;_afterOpenedAtThisLevel=new f;dialogConfigClass=X;_dialogRefConstructor;_dialogContainerType;_dialogDataToken;get openDialogs(){return this._parentDialog?this._parentDialog.openDialogs:this._openDialogsAtThisLevel}get afterOpened(){return this._parentDialog?this._parentDialog.afterOpened:this._afterOpenedAtThisLevel}_getAfterAllClosed(){let e=this._parentDialog;return e?e._getAfterAllClosed():this._afterAllClosedAtThisLevel}afterAllClosed=B(()=>this.openDialogs.length?this._getAfterAllClosed():this._getAfterAllClosed().pipe(N(void 0)));constructor(){this._dialogRefConstructor=b,this._dialogContainerType=Lt,this._dialogDataToken=ue}open(e,t){let n;t=g(g({},this._defaultOptions||new X),t),t.id=t.id||this._idGenerator.getId("mat-mdc-dialog-"),t.scrollStrategy=t.scrollStrategy||this._scrollStrategy();let o=this._dialog.open(e,fe(g({},t),{positionStrategy:Z(this._injector).centerHorizontally().centerVertically(),disableClose:!0,closePredicate:void 0,closeOnDestroy:!1,closeOnOverlayDetachments:!1,disableAnimations:this._animationsDisabled||t.enterAnimationDuration?.toLocaleString()==="0"||t.exitAnimationDuration?.toString()==="0",container:{type:this._dialogContainerType,providers:()=>[{provide:this.dialogConfigClass,useValue:t},{provide:y,useValue:t}]},templateContext:()=>({dialogRef:n}),providers:(l,s,u)=>(n=new this._dialogRefConstructor(l,t,u),n.updatePosition(t?.position),[{provide:this._dialogContainerType,useValue:u},{provide:this._dialogDataToken,useValue:s.data},{provide:this._dialogRefConstructor,useValue:n}])}));return n.componentRef=o.componentRef,n.componentInstance=o.componentInstance,this.openDialogs.push(n),this.afterOpened.next(n),n.afterClosed().subscribe(()=>{let l=this.openDialogs.indexOf(n);l>-1&&(this.openDialogs.splice(l,1),this.openDialogs.length||this._getAfterAllClosed().next())}),n}closeAll(){this._closeDialogs(this.openDialogs)}getDialogById(e){return this.openDialogs.find(t=>t.id===e)}ngOnDestroy(){this._closeDialogs(this._openDialogsAtThisLevel),this._afterAllClosedAtThisLevel.complete(),this._afterOpenedAtThisLevel.complete()}_closeDialogs(e){let t=e.length;for(;t--;)e[t].close()}static \u0275fac=function(t){return new(t||i)};static \u0275prov=j({token:i,factory:i.\u0275fac,providedIn:"root"})}return i})(),vt=(()=>{class i{dialogRef=r(b,{optional:!0});_elementRef=r(w);_dialog=r(ge);ariaLabel;type="button";dialogResult;_matDialogClose;constructor(){}ngOnInit(){this.dialogRef||(this.dialogRef=Tt(this._elementRef,this._dialog.openDialogs))}ngOnChanges(e){let t=e._matDialogClose||e._matDialogCloseResult;t&&(this.dialogResult=t.currentValue)}_onButtonClick(e){Dt(this.dialogRef,e.screenX===0&&e.screenY===0?"keyboard":"mouse",this.dialogResult)}static \u0275fac=function(t){return new(t||i)};static \u0275dir=C({type:i,selectors:[["","mat-dialog-close",""],["","matDialogClose",""]],hostVars:2,hostBindings:function(t,n){t&1&&S("click",function(l){return n._onButtonClick(l)}),t&2&&T("aria-label",n.ariaLabel||null)("type",n.type)},inputs:{ariaLabel:[0,"aria-label","ariaLabel"],type:"type",dialogResult:[0,"mat-dialog-close","dialogResult"],_matDialogClose:[0,"matDialogClose","_matDialogClose"]},exportAs:["matDialogClose"],features:[Ae]})}return i})(),Ct=(()=>{class i{_dialogRef=r(b,{optional:!0});_elementRef=r(w);_dialog=r(ge);constructor(){}ngOnInit(){this._dialogRef||(this._dialogRef=Tt(this._elementRef,this._dialog.openDialogs)),this._dialogRef&&Promise.resolve().then(()=>{this._onAdd()})}ngOnDestroy(){this._dialogRef?._containerInstance&&Promise.resolve().then(()=>{this._onRemove()})}static \u0275fac=function(t){return new(t||i)};static \u0275dir=C({type:i})}return i})(),At=(()=>{class i extends Ct{id=r(R).getId("mat-mdc-dialog-title-");_onAdd(){this._dialogRef._containerInstance?._addAriaLabelledBy?.(this.id)}_onRemove(){this._dialogRef?._containerInstance?._removeAriaLabelledBy?.(this.id)}static \u0275fac=(()=>{let e;return function(n){return(e||(e=H(i)))(n||i)}})();static \u0275dir=C({type:i,selectors:[["","mat-dialog-title",""],["","matDialogTitle",""]],hostAttrs:[1,"mat-mdc-dialog-title","mdc-dialog__title"],hostVars:1,hostBindings:function(t,n){t&2&&ne("id",n.id)},inputs:{id:"id"},exportAs:["matDialogTitle"],features:[A]})}return i})(),xt=(()=>{class i{static \u0275fac=function(t){return new(t||i)};static \u0275dir=C({type:i,selectors:[["","mat-dialog-content",""],["mat-dialog-content"],["","matDialogContent",""]],hostAttrs:[1,"mat-mdc-dialog-content","mdc-dialog__content"],features:[Oe([at])]})}return i})(),wt=(()=>{class i extends Ct{align;_onAdd(){this._dialogRef._containerInstance?._updateActionSectionCount?.(1)}_onRemove(){this._dialogRef._containerInstance?._updateActionSectionCount?.(-1)}static \u0275fac=(()=>{let e;return function(n){return(e||(e=H(i)))(n||i)}})();static \u0275dir=C({type:i,selectors:[["","mat-dialog-actions",""],["mat-dialog-actions"],["","matDialogActions",""]],hostAttrs:[1,"mat-mdc-dialog-actions","mdc-dialog__actions"],hostVars:6,hostBindings:function(t,n){t&2&&E("mat-mdc-dialog-actions-align-start",n.align==="start")("mat-mdc-dialog-actions-align-center",n.align==="center")("mat-mdc-dialog-actions-align-end",n.align==="end")},inputs:{align:"align"},features:[A]})}return i})();function Tt(i,a){let e=i.nativeElement.parentElement;for(;e&&!e.classList.contains("mat-mdc-dialog-container");)e=e.parentElement;return e?a.find(t=>t.id===e.id):null}var Ot=(()=>{class i{static \u0275fac=function(t){return new(t||i)};static \u0275mod=z({type:i});static \u0275inj=V({providers:[ge],imports:[pt,$,P,je]})}return i})();function Vt(i,a){if(i&1&&(d(0,"p"),h(1),c()),i&2){let e=I();m(),q(e.data.message)}}function Gt(i,a){if(i&1&&(d(0,"mat-error"),h(1),c()),i&2){let e=I(2);m(),q(e.form.controls.password.getError("policy"))}}function Ht(i,a){if(i&1){let e=ke();d(0,"mat-form-field",2)(1,"mat-label"),h(2,"Temporary password"),c(),ie(3,"input",7),d(4,"button",8),S("click",function(){ye(e);let n=I();return be(n.generate())}),h(5,"Generate"),c(),d(6,"mat-hint"),h(7,"The user must change it at next sign-in. Share it through a secure channel."),c(),O(8,Gt,2,1,"mat-error"),c()}if(i&2){let e=I();m(8),k(e.form.controls.password.hasError("policy")?8:-1)}}function zt(i,a){i&1&&(d(0,"mat-error"),h(1,"Please give a reason (at least 3 characters)."),c())}var pe=class i{data=r(ue);ref=r(b);form=new ze({reason:new re("",{nonNullable:!0,validators:[M.required,M.minLength(3),M.maxLength(1e3)]}),password:new re("",{nonNullable:!0,validators:this.data.withPassword?[M.required,mt]:[]})});generate(){this.form.controls.password.setValue(ht())}submit(){if(this.form.invalid)return;let{reason:a,password:e}=this.form.getRawValue();this.ref.close({reason:a.trim(),password:this.data.withPassword?e:void 0})}static \u0275fac=function(e){return new(e||i)};static \u0275cmp=v({type:i,selectors:[["ng-component"]],decls:16,vars:9,consts:[["mat-dialog-title",""],[3,"ngSubmit","formGroup"],["appearance","outline",1,"full"],["matInput","","formControlName","reason","rows","3","cdkFocusInitial",""],["align","end"],["mat-button","","type","button","mat-dialog-close",""],["mat-flat-button","","type","submit",3,"disabled"],["matInput","","formControlName","password","autocomplete","off"],["mat-button","","matSuffix","","type","button",3,"click"]],template:function(e,t){e&1&&(d(0,"h2",0),h(1),c(),d(2,"form",1),S("ngSubmit",function(){return t.submit()}),d(3,"mat-dialog-content"),O(4,Vt,2,1,"p"),O(5,Ht,9,1,"mat-form-field",2),d(6,"mat-form-field",2)(7,"mat-label"),h(8,"Reason (recorded in the audit log)"),c(),ie(9,"textarea",3),O(10,zt,2,0,"mat-error"),c()(),d(11,"mat-dialog-actions",4)(12,"button",5),h(13,"Cancel"),c(),d(14,"button",6),h(15),c()()()),e&2&&(m(),q(t.data.title),m(),te("formGroup",t.form),m(2),k(t.data.message?4:-1),m(),k(t.data.withPassword?5:-1),m(5),k(t.form.controls.reason.hasError("minlength")||t.form.controls.reason.hasError("required")?10:-1),m(4),E("danger",t.data.danger),te("disabled",t.form.invalid),m(),Re(" ",t.data.confirmLabel??"Confirm"," "))},dependencies:[Ot,vt,At,wt,xt,tt,et,Je,Xe,Ye,$e,Ze,Ke,ct,dt,Ue,We,Ve,Ge,He,Qe,qe],styles:[".full[_ngcontent-%COMP%]{width:100%}form[_ngcontent-%COMP%]{min-width:min(440px,80vw)}"],changeDetection:0})};function Qi(i,a){return i.open(pe,{data:a,autoFocus:"dialog"}).afterClosed()}export{ge as a,Qi as b};
