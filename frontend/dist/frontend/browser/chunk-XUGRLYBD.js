import{a as W}from"./chunk-LJSTTFX2.js";import{a as tt,b as et}from"./chunk-DSDORQP6.js";import{e as at,i as nt,j as ot}from"./chunk-HTVCGHS6.js";import{H as K}from"./chunk-SW7XBUG3.js";import{a as it}from"./chunk-CS36JUXR.js";import{O as X,Q as Y,v as J}from"./chunk-MVNFUC75.js";import{D as k,Ga as G,Ha as c,I as L,Ia as u,Ja as h,L as B,La as $,Ma as U,Na as H,O as E,Oa as p,P as F,Pa as n,Q as N,Qa as s,R as b,Ra as x,Sb as Z,T as _,U as f,Ub as D,V as v,Vb as z,W as A,Ya as I,_ as V,_a as m,ab as d,ba as g,d as y,f as T,k as O,kb as Q,ma as r,ob as S,pb as q,qb as C,va as R,wa as j,x as w}from"./chunk-ZWUSPUI7.js";function st(i,o){if(i&1&&(n(0,"mat-option",17),S(1),s()),i&2){let t=o.$implicit;p("value",t),r(),C(" ",t," ")}}function lt(i,o){if(i&1){let t=I();n(0,"mat-form-field",14)(1,"mat-select",16,0),m("selectionChange",function(e){_(t);let l=d(2);return f(l._changePageSize(e.value))}),U(3,st,2,2,"mat-option",17,$),s(),n(5,"div",18),m("click",function(){_(t);let e=Q(2);return f(e.open())}),s()()}if(i&2){let t=d(2);p("appearance",t._formFieldAppearance)("color",t.color),r(),p("value",t.pageSize)("disabled",t.disabled),G("aria-labelledby",t._pageSizeLabelId),p("panelClass",t.selectConfig.panelClass||"")("disableOptionCentering",t.selectConfig.disableOptionCentering),r(2),H(t._displayedPageSizeOptions)}}function pt(i,o){if(i&1&&(n(0,"div",15),S(1),s()),i&2){let t=d(2);r(),q(t.pageSize)}}function dt(i,o){if(i&1&&(n(0,"div",3)(1,"div",13),S(2),s(),u(3,lt,6,7,"mat-form-field",14),u(4,pt,2,1,"div",15),s()),i&2){let t=d();r(),c("id",t._pageSizeLabelId),r(),C(" ",t._intl.itemsPerPageLabel," "),r(),h(t._displayedPageSizeOptions.length>1?3:-1),r(),h(t._displayedPageSizeOptions.length<=1?4:-1)}}function gt(i,o){if(i&1){let t=I();n(0,"button",19),m("click",function(){_(t);let e=d();return f(e._buttonClicked(0,e._previousButtonsDisabled()))}),v(),n(1,"svg",8),x(2,"path",20),s()()}if(i&2){let t=d();p("matTooltip",t._intl.firstPageLabel)("matTooltipDisabled",t._previousButtonsDisabled())("disabled",t._previousButtonsDisabled())("tabindex",t._previousButtonsDisabled()?-1:null),c("aria-label",t._intl.firstPageLabel)}}function mt(i,o){if(i&1){let t=I();n(0,"button",21),m("click",function(){_(t);let e=d();return f(e._buttonClicked(e.getNumberOfPages()-1,e._nextButtonsDisabled()))}),v(),n(1,"svg",8),x(2,"path",22),s()()}if(i&2){let t=d();p("matTooltip",t._intl.lastPageLabel)("matTooltipDisabled",t._nextButtonsDisabled())("disabled",t._nextButtonsDisabled())("tabindex",t._nextButtonsDisabled()?-1:null),c("aria-label",t._intl.lastPageLabel)}}var ct=(()=>{class i{changes=new y;itemsPerPageLabel="Items per page:";nextPageLabel="Next page";previousPageLabel="Previous page";firstPageLabel="First page";lastPageLabel="Last page";getRangeLabel=(t,a,e)=>{if(e==0||a==0)return`0 of ${e}`;e=Math.max(e,0);let l=t*a,P=l<e?Math.min(l+a,e):l+a;return`${l+1} \u2013 ${P} of ${e}`};static \u0275fac=function(a){return new(a||i)};static \u0275prov=E({token:i,factory:i.\u0275fac,providedIn:"root"})}return i})(),ut=50;var ht=new N("MAT_PAGINATOR_DEFAULT_OPTIONS"),bt=(()=>{class i{_intl=b(ct);_changeDetectorRef=b(Z);_formFieldAppearance;_pageSizeLabelId=b(J).getId("mat-paginator-page-size-label-");_intlChanges;_isInitialized=!1;_initializedStream=new T(1);color;get pageIndex(){return this._pageIndex}set pageIndex(t){this._pageIndex=Math.max(t||0,0),this._changeDetectorRef.markForCheck()}_pageIndex=0;get length(){return this._length}set length(t){this._length=t||0,this._changeDetectorRef.markForCheck()}_length=0;get pageSize(){return this._pageSize}set pageSize(t){this._pageSize=Math.max(t||0,0),this._updateDisplayedPageSizeOptions()}_pageSize;get pageSizeOptions(){return this._pageSizeOptions}set pageSizeOptions(t){this._pageSizeOptions=(t||[]).map(a=>z(a,0)),this._updateDisplayedPageSizeOptions()}_pageSizeOptions=[];hidePageSize=!1;showFirstLastButtons=!1;selectConfig={};disabled=!1;page=new V;_displayedPageSizeOptions;initialized=this._initializedStream;constructor(){let t=this._intl,a=b(ht,{optional:!0});if(this._intlChanges=t.changes.subscribe(()=>this._changeDetectorRef.markForCheck()),a){let{pageSize:e,pageSizeOptions:l,hidePageSize:P,showFirstLastButtons:M}=a;e!=null&&(this._pageSize=e),l!=null&&(this._pageSizeOptions=l),P!=null&&(this.hidePageSize=P),M!=null&&(this.showFirstLastButtons=M)}this._formFieldAppearance=a?.formFieldAppearance||"outline"}ngOnInit(){this._isInitialized=!0,this._updateDisplayedPageSizeOptions(),this._initializedStream.next()}ngOnDestroy(){this._initializedStream.complete(),this._intlChanges.unsubscribe()}nextPage(){this.hasNextPage()&&this._navigate(this.pageIndex+1)}previousPage(){this.hasPreviousPage()&&this._navigate(this.pageIndex-1)}firstPage(){this.hasPreviousPage()&&this._navigate(0)}lastPage(){this.hasNextPage()&&this._navigate(this.getNumberOfPages()-1)}hasPreviousPage(){return this.pageIndex>=1&&this.pageSize!=0}hasNextPage(){let t=this.getNumberOfPages()-1;return this.pageIndex<t&&this.pageSize!=0}getNumberOfPages(){return this.pageSize?Math.ceil(this.length/this.pageSize):0}_changePageSize(t){let a=this.pageIndex*this.pageSize,e=this.pageIndex;this.pageIndex=Math.floor(a/t)||0,this.pageSize=t,this._emitPageEvent(e)}_nextButtonsDisabled(){return this.disabled||!this.hasNextPage()}_previousButtonsDisabled(){return this.disabled||!this.hasPreviousPage()}_updateDisplayedPageSizeOptions(){this._isInitialized&&(this.pageSize||(this._pageSize=this.pageSizeOptions.length!=0?this.pageSizeOptions[0]:ut),this._displayedPageSizeOptions=this.pageSizeOptions.slice(),this._displayedPageSizeOptions.indexOf(this.pageSize)===-1&&this._displayedPageSizeOptions.push(this.pageSize),this._displayedPageSizeOptions.sort((t,a)=>t-a),this._changeDetectorRef.markForCheck())}_emitPageEvent(t){this.page.emit({previousPageIndex:t,pageIndex:this.pageIndex,pageSize:this.pageSize,length:this.length})}_navigate(t){let a=this.pageIndex;t!==a&&(this.pageIndex=t,this._emitPageEvent(a))}_buttonClicked(t,a){a||this._navigate(t)}static \u0275fac=function(a){return new(a||i)};static \u0275cmp=R({type:i,selectors:[["mat-paginator"]],hostAttrs:["role","group",1,"mat-mdc-paginator"],inputs:{color:"color",pageIndex:[2,"pageIndex","pageIndex",z],length:[2,"length","length",z],pageSize:[2,"pageSize","pageSize",z],pageSizeOptions:"pageSizeOptions",hidePageSize:[2,"hidePageSize","hidePageSize",D],showFirstLastButtons:[2,"showFirstLastButtons","showFirstLastButtons",D],selectConfig:"selectConfig",disabled:[2,"disabled","disabled",D]},outputs:{page:"page"},exportAs:["matPaginator"],decls:14,vars:14,consts:[["selectRef",""],[1,"mat-mdc-paginator-outer-container"],[1,"mat-mdc-paginator-container"],[1,"mat-mdc-paginator-page-size"],[1,"mat-mdc-paginator-range-actions"],["aria-atomic","true","aria-live","polite","role","status",1,"mat-mdc-paginator-range-label"],["matIconButton","","type","button","matTooltipPosition","above","disabledInteractive","",1,"mat-mdc-paginator-navigation-first",3,"matTooltip","matTooltipDisabled","disabled","tabindex"],["matIconButton","","type","button","matTooltipPosition","above","disabledInteractive","",1,"mat-mdc-paginator-navigation-previous",3,"click","matTooltip","matTooltipDisabled","disabled","tabindex"],["viewBox","0 0 24 24","focusable","false","aria-hidden","true",1,"mat-mdc-paginator-icon"],["d","M15.41 7.41L14 6l-6 6 6 6 1.41-1.41L10.83 12z"],["matIconButton","","type","button","matTooltipPosition","above","disabledInteractive","",1,"mat-mdc-paginator-navigation-next",3,"click","matTooltip","matTooltipDisabled","disabled","tabindex"],["d","M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"],["matIconButton","","type","button","matTooltipPosition","above","disabledInteractive","",1,"mat-mdc-paginator-navigation-last",3,"matTooltip","matTooltipDisabled","disabled","tabindex"],["aria-hidden","true",1,"mat-mdc-paginator-page-size-label"],[1,"mat-mdc-paginator-page-size-select",3,"appearance","color"],[1,"mat-mdc-paginator-page-size-value"],["hideSingleSelectionIndicator","",3,"selectionChange","value","disabled","aria-labelledby","panelClass","disableOptionCentering"],[3,"value"],[1,"mat-mdc-paginator-touch-target",3,"click"],["matIconButton","","type","button","matTooltipPosition","above","disabledInteractive","",1,"mat-mdc-paginator-navigation-first",3,"click","matTooltip","matTooltipDisabled","disabled","tabindex"],["d","M18.41 16.59L13.82 12l4.59-4.59L17 6l-6 6 6 6zM6 6h2v12H6z"],["matIconButton","","type","button","matTooltipPosition","above","disabledInteractive","",1,"mat-mdc-paginator-navigation-last",3,"click","matTooltip","matTooltipDisabled","disabled","tabindex"],["d","M5.59 7.41L10.18 12l-4.59 4.59L7 18l6-6-6-6zM16 6h2v12h-2z"]],template:function(a,e){a&1&&(n(0,"div",1)(1,"div",2),u(2,dt,5,4,"div",3),n(3,"div",4)(4,"div",5),S(5),s(),u(6,gt,3,5,"button",6),n(7,"button",7),m("click",function(){return e._buttonClicked(e.pageIndex-1,e._previousButtonsDisabled())}),v(),n(8,"svg",8),x(9,"path",9),s()(),A(),n(10,"button",10),m("click",function(){return e._buttonClicked(e.pageIndex+1,e._nextButtonsDisabled())}),v(),n(11,"svg",8),x(12,"path",11),s()(),u(13,mt,3,5,"button",12),s()()()),a&2&&(r(2),h(e.hidePageSize?-1:2),r(3),C(" ",e._intl.getRangeLabel(e.pageIndex,e.pageSize,e.length)," "),r(),h(e.showFirstLastButtons?6:-1),r(),p("matTooltip",e._intl.previousPageLabel)("matTooltipDisabled",e._previousButtonsDisabled())("disabled",e._previousButtonsDisabled())("tabindex",e._previousButtonsDisabled()?-1:null),c("aria-label",e._intl.previousPageLabel),r(3),p("matTooltip",e._intl.nextPageLabel)("matTooltipDisabled",e._nextButtonsDisabled())("disabled",e._nextButtonsDisabled())("tabindex",e._nextButtonsDisabled()?-1:null),c("aria-label",e._intl.nextPageLabel),r(3),h(e.showFirstLastButtons?13:-1))},dependencies:[K,nt,at,X,tt],styles:[`.mat-mdc-paginator {
  display: block;
  -moz-osx-font-smoothing: grayscale;
  -webkit-font-smoothing: antialiased;
  color: var(--mat-paginator-container-text-color, var(--mat-sys-on-surface));
  background-color: var(--mat-paginator-container-background-color, var(--mat-sys-surface));
  font-family: var(--mat-paginator-container-text-font, var(--mat-sys-body-small-font));
  line-height: var(--mat-paginator-container-text-line-height, var(--mat-sys-body-small-line-height));
  font-size: var(--mat-paginator-container-text-size, var(--mat-sys-body-small-size));
  font-weight: var(--mat-paginator-container-text-weight, var(--mat-sys-body-small-weight));
  letter-spacing: var(--mat-paginator-container-text-tracking, var(--mat-sys-body-small-tracking));
  --mat-form-field-container-height: var(--mat-paginator-form-field-container-height, 40px);
  --mat-form-field-container-vertical-padding: var(--mat-paginator-form-field-container-vertical-padding, 8px);
}
.mat-mdc-paginator .mat-mdc-select-value {
  font-size: var(--mat-paginator-select-trigger-text-size, var(--mat-sys-body-small-size));
}
.mat-mdc-paginator .mat-mdc-form-field-subscript-wrapper {
  display: none;
}
.mat-mdc-paginator .mat-mdc-select {
  line-height: 1.5;
}

.mat-mdc-paginator-outer-container {
  display: flex;
}

.mat-mdc-paginator-container {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding: 0 8px;
  flex-wrap: wrap;
  width: 100%;
  min-height: var(--mat-paginator-container-size, 56px);
}

.mat-mdc-paginator-page-size {
  display: flex;
  align-items: baseline;
  margin-right: 8px;
}
[dir=rtl] .mat-mdc-paginator-page-size {
  margin-right: 0;
  margin-left: 8px;
}

.mat-mdc-paginator-page-size-label {
  margin: 0 4px;
}

.mat-mdc-paginator-page-size-select {
  margin: 0 4px;
  width: var(--mat-paginator-page-size-select-width, 84px);
}

.mat-mdc-paginator-range-label {
  margin: 0 32px 0 24px;
}

.mat-mdc-paginator-range-actions {
  display: flex;
  align-items: center;
}

.mat-mdc-paginator-icon {
  display: inline-block;
  width: 28px;
  fill: var(--mat-paginator-enabled-icon-color, var(--mat-sys-on-surface-variant));
}
.mat-mdc-icon-button[aria-disabled] .mat-mdc-paginator-icon {
  fill: var(--mat-paginator-disabled-icon-color, color-mix(in srgb, var(--mat-sys-on-surface) 38%, transparent));
}
[dir=rtl] .mat-mdc-paginator-icon {
  transform: rotate(180deg);
}

@media (forced-colors: active) {
  .mat-mdc-icon-button[aria-disabled] .mat-mdc-paginator-icon,
  .mat-mdc-paginator-icon {
    fill: currentColor;
  }
  .mat-mdc-paginator-range-actions .mat-mdc-icon-button {
    outline: solid 1px;
  }
  .mat-mdc-paginator-range-actions .mat-mdc-icon-button[aria-disabled] {
    color: GrayText;
  }
}
.mat-mdc-paginator-touch-target {
  display: var(--mat-paginator-touch-target-display, block);
  position: absolute;
  top: 50%;
  left: 50%;
  width: var(--mat-paginator-page-size-select-width, 84px);
  height: var(--mat-paginator-page-size-select-touch-target-height, 48px);
  background-color: transparent;
  transform: translate(-50%, -50%);
  cursor: pointer;
}
`],encapsulation:2,changeDetection:0})}return i})(),Et=(()=>{class i{static \u0275fac=function(a){return new(a||i)};static \u0275mod=j({type:i});static \u0275inj=F({imports:[Y,ot,et,bt]})}return i})();var rt=class{items=g([]);total=g(0);loading=g(!1);error=g(null);page=g(1);pageSize=g(25);sort=g(null);trigger=new y;constructor(o,t,a=null){this.sort.set(a),this.trigger.pipe(B(()=>{this.loading.set(!0),this.error.set(null)}),L(()=>o({page:this.page(),page_size:this.pageSize(),sort:this.sort()}).pipe(w(e=>(this.error.set(it.from(e)),O(null))),k(()=>this.loading.set(!1)))),W(t)).subscribe(e=>{this.loading.set(!1),e&&(this.items.set(e.items),this.total.set(e.total))})}load(){this.trigger.next()}reset(){this.page.set(1),this.load()}onPage(o){this.page.set(o.pageIndex+1),this.pageSize.set(o.pageSize),this.load()}onSort(o){this.sort.set(o.direction?`${o.direction==="desc"?"-":""}${o.active}`:null),this.reset()}};export{bt as a,Et as b,rt as c};
