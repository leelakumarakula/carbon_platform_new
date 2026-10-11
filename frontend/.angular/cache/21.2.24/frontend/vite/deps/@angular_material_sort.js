import {
  CdkColumnDef
} from "./chunk-FXHHI5OX.js";
import "./chunk-YGIWM5MO.js";
import {
  _StructuralStylesLoader
} from "./chunk-H742VBNK.js";
import {
  AriaDescriber,
  ENTER,
  FocusMonitor,
  SPACE
} from "./chunk-7FBJIU3R.js";
import "./chunk-XA6252L2.js";
import "./chunk-6OTIV4AS.js";
import "./chunk-V5JFTKFM.js";
import {
  _animationsDisabled
} from "./chunk-BKYXKDCC.js";
import "./chunk-MLHI5STG.js";
import "./chunk-5MX34KEC.js";
import "./chunk-GUGIMSVJ.js";
import {
  _CdkPrivateStyleLoader
} from "./chunk-JBY2FT5Z.js";
import "./chunk-ENTCXOS7.js";
import {
  BidiModule
} from "./chunk-OX6GT3YL.js";
import "./chunk-GFQIOWM6.js";
import "./chunk-N4DOILP3.js";
import "./chunk-4KOQEFJJ.js";
import "./chunk-YRILHKUY.js";
import "./chunk-AH2YPTO2.js";
import "./chunk-LY3YZEIF.js";
import {
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  Directive,
  ElementRef,
  Inject,
  Injectable,
  Input,
  NgModule,
  Optional,
  Output,
  ViewEncapsulation,
  booleanAttribute,
  setClassMetadata,
  ɵɵNgOnChangesFeature,
  ɵɵadvance,
  ɵɵattribute,
  ɵɵclassProp,
  ɵɵconditional,
  ɵɵconditionalCreate,
  ɵɵdefineComponent,
  ɵɵdefineDirective,
  ɵɵdefineNgModule,
  ɵɵdirectiveInject,
  ɵɵdomElement,
  ɵɵdomElementEnd,
  ɵɵdomElementStart,
  ɵɵlistener,
  ɵɵprojection,
  ɵɵprojectionDef
} from "./chunk-N5ZPR4X7.js";
import {
  EventEmitter,
  InjectionToken,
  inject,
  signal,
  ɵɵdefineInjectable,
  ɵɵdefineInjector,
  ɵɵnamespaceSVG
} from "./chunk-UNRALM3K.js";
import {
  ReplaySubject,
  Subject,
  merge
} from "./chunk-RSS3ODKE.js";
import "./chunk-75NUGXPU.js";

// node_modules/@angular/material/fesm2022/sort.mjs
var _c0 = ["mat-sort-header", ""];
var _c1 = ["*", [["", "matSortHeaderIcon", ""]]];
var _c2 = ["*", "[matSortHeaderIcon]"];
function MatSortHeader_Conditional_3_ProjectionFallback_1_Template(rf, ctx) {
  if (rf & 1) {
    ɵɵnamespaceSVG();
    ɵɵdomElementStart(0, "svg", 3);
    ɵɵdomElement(1, "path", 4);
    ɵɵdomElementEnd();
  }
}
function MatSortHeader_Conditional_3_Template(rf, ctx) {
  if (rf & 1) {
    ɵɵdomElementStart(0, "div", 2);
    ɵɵprojection(1, 1, null, MatSortHeader_Conditional_3_ProjectionFallback_1_Template, 2, 0);
    ɵɵdomElementEnd();
  }
}
function getSortDuplicateSortableIdError(id) {
  return Error(`Cannot have two MatSortables with the same id (${id}).`);
}
function getSortHeaderNotContainedWithinSortError() {
  return Error(`MatSortHeader must be placed within a parent element with the MatSort directive.`);
}
function getSortHeaderMissingIdError() {
  return Error(`MatSortHeader must be provided with a unique id.`);
}
function getSortInvalidDirectionError(direction) {
  return Error(`${direction} is not a valid sort direction ('asc' or 'desc').`);
}
var MAT_SORT_DEFAULT_OPTIONS = new InjectionToken("MAT_SORT_DEFAULT_OPTIONS");
var MatSort = class _MatSort {
  _defaultOptions;
  _initializedStream = new ReplaySubject(1);
  sortables = /* @__PURE__ */ new Map();
  _stateChanges = new Subject();
  active;
  start = "asc";
  get direction() {
    return this._direction;
  }
  set direction(direction) {
    if (direction && direction !== "asc" && direction !== "desc" && (typeof ngDevMode === "undefined" || ngDevMode)) {
      throw getSortInvalidDirectionError(direction);
    }
    this._direction = direction;
  }
  _direction = "";
  disableClear;
  disabled = false;
  sortChange = new EventEmitter();
  initialized = this._initializedStream;
  constructor(_defaultOptions) {
    this._defaultOptions = _defaultOptions;
  }
  register(sortable) {
    if (typeof ngDevMode === "undefined" || ngDevMode) {
      if (!sortable.id) {
        throw getSortHeaderMissingIdError();
      }
      if (this.sortables.has(sortable.id)) {
        throw getSortDuplicateSortableIdError(sortable.id);
      }
    }
    this.sortables.set(sortable.id, sortable);
  }
  deregister(sortable) {
    this.sortables.delete(sortable.id);
  }
  sort(sortable) {
    if (this.active != sortable.id) {
      this.active = sortable.id;
      this.direction = sortable.start ? sortable.start : this.start;
    } else {
      this.direction = this.getNextSortDirection(sortable);
    }
    this.sortChange.emit({
      active: this.active,
      direction: this.direction
    });
  }
  getNextSortDirection(sortable) {
    if (!sortable) {
      return "";
    }
    const disableClear = sortable?.disableClear ?? this.disableClear ?? !!this._defaultOptions?.disableClear;
    let sortDirectionCycle = getSortDirectionCycle(sortable.start || this.start, disableClear);
    let nextDirectionIndex = sortDirectionCycle.indexOf(this.direction) + 1;
    if (nextDirectionIndex >= sortDirectionCycle.length) {
      nextDirectionIndex = 0;
    }
    return sortDirectionCycle[nextDirectionIndex];
  }
  ngOnInit() {
    this._initializedStream.next();
  }
  ngOnChanges() {
    this._stateChanges.next();
  }
  ngOnDestroy() {
    this._stateChanges.complete();
    this._initializedStream.complete();
  }
  static ɵfac = function MatSort_Factory(__ngFactoryType__) {
    return new (__ngFactoryType__ || _MatSort)(ɵɵdirectiveInject(MAT_SORT_DEFAULT_OPTIONS, 8));
  };
  static ɵdir = ɵɵdefineDirective({
    type: _MatSort,
    selectors: [["", "matSort", ""]],
    hostAttrs: [1, "mat-sort"],
    inputs: {
      active: [0, "matSortActive", "active"],
      start: [0, "matSortStart", "start"],
      direction: [0, "matSortDirection", "direction"],
      disableClear: [2, "matSortDisableClear", "disableClear", booleanAttribute],
      disabled: [2, "matSortDisabled", "disabled", booleanAttribute]
    },
    outputs: {
      sortChange: "matSortChange"
    },
    exportAs: ["matSort"],
    features: [ɵɵNgOnChangesFeature]
  });
};
(() => {
  (typeof ngDevMode === "undefined" || ngDevMode) && setClassMetadata(MatSort, [{
    type: Directive,
    args: [{
      selector: "[matSort]",
      exportAs: "matSort",
      host: {
        "class": "mat-sort"
      }
    }]
  }], () => [{
    type: void 0,
    decorators: [{
      type: Optional
    }, {
      type: Inject,
      args: [MAT_SORT_DEFAULT_OPTIONS]
    }]
  }], {
    active: [{
      type: Input,
      args: ["matSortActive"]
    }],
    start: [{
      type: Input,
      args: ["matSortStart"]
    }],
    direction: [{
      type: Input,
      args: ["matSortDirection"]
    }],
    disableClear: [{
      type: Input,
      args: [{
        alias: "matSortDisableClear",
        transform: booleanAttribute
      }]
    }],
    disabled: [{
      type: Input,
      args: [{
        alias: "matSortDisabled",
        transform: booleanAttribute
      }]
    }],
    sortChange: [{
      type: Output,
      args: ["matSortChange"]
    }]
  });
})();
function getSortDirectionCycle(start, disableClear) {
  let sortOrder = ["asc", "desc"];
  if (start == "desc") {
    sortOrder.reverse();
  }
  if (!disableClear) {
    sortOrder.push("");
  }
  return sortOrder;
}
var MatSortHeader = class _MatSortHeader {
  _sort = inject(MatSort, {
    optional: true
  });
  _columnDef = inject(CdkColumnDef, {
    optional: true
  });
  _changeDetectorRef = inject(ChangeDetectorRef);
  _focusMonitor = inject(FocusMonitor);
  _elementRef = inject(ElementRef);
  _ariaDescriber = inject(AriaDescriber, {
    optional: true
  });
  _renderChanges;
  _animationsDisabled = _animationsDisabled();
  _recentlyCleared = signal(null, ...ngDevMode ? [{
    debugName: "_recentlyCleared"
  }] : []);
  _sortButton;
  id;
  arrowPosition = "after";
  start;
  disabled = false;
  get sortActionDescription() {
    return this._sortActionDescription;
  }
  set sortActionDescription(value) {
    this._updateSortActionDescription(value);
  }
  _sortActionDescription = "Sort";
  disableClear;
  constructor() {
    inject(_CdkPrivateStyleLoader).load(_StructuralStylesLoader);
    const defaultOptions = inject(MAT_SORT_DEFAULT_OPTIONS, {
      optional: true
    });
    if (!this._sort && (typeof ngDevMode === "undefined" || ngDevMode)) {
      throw getSortHeaderNotContainedWithinSortError();
    }
    if (defaultOptions?.arrowPosition) {
      this.arrowPosition = defaultOptions?.arrowPosition;
    }
  }
  ngOnInit() {
    if (!this.id && this._columnDef) {
      this.id = this._columnDef.name;
    }
    this._sort.register(this);
    this._renderChanges = merge(this._sort._stateChanges, this._sort.sortChange).subscribe(() => this._changeDetectorRef.markForCheck());
    this._sortButton = this._elementRef.nativeElement.querySelector(".mat-sort-header-container");
    this._updateSortActionDescription(this._sortActionDescription);
  }
  ngAfterViewInit() {
    this._focusMonitor.monitor(this._elementRef, true).subscribe(() => {
      Promise.resolve().then(() => this._recentlyCleared.set(null));
    });
  }
  ngOnDestroy() {
    this._focusMonitor.stopMonitoring(this._elementRef);
    this._sort.deregister(this);
    this._renderChanges?.unsubscribe();
    if (this._sortButton) {
      this._ariaDescriber?.removeDescription(this._sortButton, this._sortActionDescription);
    }
  }
  _toggleOnInteraction() {
    if (!this._isDisabled()) {
      const wasSorted = this._isSorted();
      const prevDirection = this._sort.direction;
      this._sort.sort(this);
      this._recentlyCleared.set(wasSorted && !this._isSorted() ? prevDirection : null);
    }
  }
  _handleKeydown(event) {
    if (event.keyCode === SPACE || event.keyCode === ENTER) {
      event.preventDefault();
      this._toggleOnInteraction();
    }
  }
  _isSorted() {
    return this._sort.active == this.id && (this._sort.direction === "asc" || this._sort.direction === "desc");
  }
  _isDisabled() {
    return this._sort.disabled || this.disabled;
  }
  _getAriaSortAttribute() {
    if (!this._isSorted()) {
      return "none";
    }
    return this._sort.direction == "asc" ? "ascending" : "descending";
  }
  _renderArrow() {
    return !this._isDisabled() || this._isSorted();
  }
  _updateSortActionDescription(newDescription) {
    if (this._sortButton) {
      this._ariaDescriber?.removeDescription(this._sortButton, this._sortActionDescription);
      this._ariaDescriber?.describe(this._sortButton, newDescription);
    }
    this._sortActionDescription = newDescription;
  }
  static ɵfac = function MatSortHeader_Factory(__ngFactoryType__) {
    return new (__ngFactoryType__ || _MatSortHeader)();
  };
  static ɵcmp = ɵɵdefineComponent({
    type: _MatSortHeader,
    selectors: [["", "mat-sort-header", ""]],
    hostAttrs: [1, "mat-sort-header"],
    hostVars: 3,
    hostBindings: function MatSortHeader_HostBindings(rf, ctx) {
      if (rf & 1) {
        ɵɵlistener("click", function MatSortHeader_click_HostBindingHandler() {
          return ctx._toggleOnInteraction();
        })("keydown", function MatSortHeader_keydown_HostBindingHandler($event) {
          return ctx._handleKeydown($event);
        })("mouseleave", function MatSortHeader_mouseleave_HostBindingHandler() {
          return ctx._recentlyCleared.set(null);
        });
      }
      if (rf & 2) {
        ɵɵattribute("aria-sort", ctx._getAriaSortAttribute());
        ɵɵclassProp("mat-sort-header-disabled", ctx._isDisabled());
      }
    },
    inputs: {
      id: [0, "mat-sort-header", "id"],
      arrowPosition: "arrowPosition",
      start: "start",
      disabled: [2, "disabled", "disabled", booleanAttribute],
      sortActionDescription: "sortActionDescription",
      disableClear: [2, "disableClear", "disableClear", booleanAttribute]
    },
    exportAs: ["matSortHeader"],
    attrs: _c0,
    ngContentSelectors: _c2,
    decls: 4,
    vars: 17,
    consts: [[1, "mat-sort-header-container", "mat-focus-indicator"], [1, "mat-sort-header-content"], [1, "mat-sort-header-arrow"], ["viewBox", "0 -960 960 960", "focusable", "false", "aria-hidden", "true"], ["d", "M440-240v-368L296-464l-56-56 240-240 240 240-56 56-144-144v368h-80Z"]],
    template: function MatSortHeader_Template(rf, ctx) {
      if (rf & 1) {
        ɵɵprojectionDef(_c1);
        ɵɵdomElementStart(0, "div", 0)(1, "div", 1);
        ɵɵprojection(2);
        ɵɵdomElementEnd();
        ɵɵconditionalCreate(3, MatSortHeader_Conditional_3_Template, 3, 0, "div", 2);
        ɵɵdomElementEnd();
      }
      if (rf & 2) {
        ɵɵclassProp("mat-sort-header-sorted", ctx._isSorted())("mat-sort-header-position-before", ctx.arrowPosition === "before")("mat-sort-header-descending", ctx._sort.direction === "desc")("mat-sort-header-ascending", ctx._sort.direction === "asc")("mat-sort-header-recently-cleared-ascending", ctx._recentlyCleared() === "asc")("mat-sort-header-recently-cleared-descending", ctx._recentlyCleared() === "desc")("mat-sort-header-animations-disabled", ctx._animationsDisabled);
        ɵɵattribute("tabindex", ctx._isDisabled() ? null : 0)("role", ctx._isDisabled() ? null : "button");
        ɵɵadvance(3);
        ɵɵconditional(ctx._renderArrow() ? 3 : -1);
      }
    },
    styles: [".mat-sort-header {\n  cursor: pointer;\n}\n\n.mat-sort-header-disabled {\n  cursor: default;\n}\n\n.mat-sort-header-container {\n  display: flex;\n  align-items: center;\n  letter-spacing: normal;\n  outline: 0;\n}\n[mat-sort-header].cdk-keyboard-focused .mat-sort-header-container, [mat-sort-header].cdk-program-focused .mat-sort-header-container {\n  border-bottom: solid 1px currentColor;\n}\n.mat-sort-header-container::before {\n  margin: calc(calc(var(--mat-focus-indicator-border-width, 3px) + 2px) * -1);\n}\n\n.mat-sort-header-content {\n  display: flex;\n  align-items: center;\n}\n\n.mat-sort-header-position-before {\n  flex-direction: row-reverse;\n}\n\n@keyframes _mat-sort-header-recently-cleared-ascending {\n  from {\n    transform: translateY(0);\n    opacity: 1;\n  }\n  to {\n    transform: translateY(-25%);\n    opacity: 0;\n  }\n}\n@keyframes _mat-sort-header-recently-cleared-descending {\n  from {\n    transform: translateY(0) rotate(180deg);\n    opacity: 1;\n  }\n  to {\n    transform: translateY(25%) rotate(180deg);\n    opacity: 0;\n  }\n}\n.mat-sort-header-arrow {\n  height: 12px;\n  width: 12px;\n  position: relative;\n  transition: transform 225ms cubic-bezier(0.4, 0, 0.2, 1), opacity 225ms cubic-bezier(0.4, 0, 0.2, 1);\n  opacity: 0;\n  overflow: visible;\n  color: var(--mat-sort-arrow-color, var(--mat-sys-on-surface));\n}\n.mat-sort-header.cdk-keyboard-focused .mat-sort-header-arrow, .mat-sort-header.cdk-program-focused .mat-sort-header-arrow, .mat-sort-header:hover .mat-sort-header-arrow {\n  opacity: 0.54;\n}\n.mat-sort-header .mat-sort-header-sorted .mat-sort-header-arrow {\n  opacity: 1;\n}\n.mat-sort-header-descending .mat-sort-header-arrow {\n  transform: rotate(180deg);\n}\n.mat-sort-header-recently-cleared-ascending .mat-sort-header-arrow {\n  transform: translateY(-25%);\n}\n.mat-sort-header-recently-cleared-ascending .mat-sort-header-arrow {\n  transition: none;\n  animation: _mat-sort-header-recently-cleared-ascending 225ms cubic-bezier(0.4, 0, 0.2, 1) forwards;\n}\n.mat-sort-header-recently-cleared-descending .mat-sort-header-arrow {\n  transition: none;\n  animation: _mat-sort-header-recently-cleared-descending 225ms cubic-bezier(0.4, 0, 0.2, 1) forwards;\n}\n.mat-sort-header-animations-disabled .mat-sort-header-arrow {\n  transition-duration: 0ms;\n  animation-duration: 0ms;\n}\n.mat-sort-header-arrow > svg, .mat-sort-header-arrow [matSortHeaderIcon] {\n  width: 24px;\n  height: 24px;\n  fill: currentColor;\n  position: absolute;\n  top: 50%;\n  left: 50%;\n  margin: -12px 0 0 -12px;\n  transform: translateZ(0);\n}\n.mat-sort-header-arrow, [dir=rtl] .mat-sort-header-position-before .mat-sort-header-arrow {\n  margin: 0 0 0 6px;\n}\n.mat-sort-header-position-before .mat-sort-header-arrow, [dir=rtl] .mat-sort-header-arrow {\n  margin: 0 6px 0 0;\n}\n"],
    encapsulation: 2,
    changeDetection: 0
  });
};
(() => {
  (typeof ngDevMode === "undefined" || ngDevMode) && setClassMetadata(MatSortHeader, [{
    type: Component,
    args: [{
      selector: "[mat-sort-header]",
      exportAs: "matSortHeader",
      host: {
        "class": "mat-sort-header",
        "(click)": "_toggleOnInteraction()",
        "(keydown)": "_handleKeydown($event)",
        "(mouseleave)": "_recentlyCleared.set(null)",
        "[attr.aria-sort]": "_getAriaSortAttribute()",
        "[class.mat-sort-header-disabled]": "_isDisabled()"
      },
      encapsulation: ViewEncapsulation.None,
      changeDetection: ChangeDetectionStrategy.OnPush,
      template: `<!--
  We set the \`tabindex\` on an element inside the table header, rather than the header itself,
  because of a bug in NVDA where having a \`tabindex\` on a \`th\` breaks keyboard navigation in the
  table (see https://github.com/nvaccess/nvda/issues/7718). This allows for the header to both
  be focusable, and have screen readers read out its \`aria-sort\` state. We prefer this approach
  over having a button with an \`aria-label\` inside the header, because the button's \`aria-label\`
  will be read out as the user is navigating the table's cell (see #13012).

  The approach is based off of: https://dequeuniversity.com/library/aria/tables/sf-sortable-grid
-->
<div class="mat-sort-header-container mat-focus-indicator"
     [class.mat-sort-header-sorted]="_isSorted()"
     [class.mat-sort-header-position-before]="arrowPosition === 'before'"
     [class.mat-sort-header-descending]="_sort.direction === 'desc'"
     [class.mat-sort-header-ascending]="_sort.direction === 'asc'"
     [class.mat-sort-header-recently-cleared-ascending]="_recentlyCleared() === 'asc'"
     [class.mat-sort-header-recently-cleared-descending]="_recentlyCleared() === 'desc'"
     [class.mat-sort-header-animations-disabled]="_animationsDisabled"
     [attr.tabindex]="_isDisabled() ? null : 0"
     [attr.role]="_isDisabled() ? null : 'button'">

  <!--
    TODO(crisbeto): this div isn't strictly necessary, but we have to keep it due to a large
    number of screenshot diff failures. It should be removed eventually. Note that the difference
    isn't visible with a shorter header, but once it breaks up into multiple lines, this element
    causes it to be center-aligned, whereas removing it will keep the text to the left.
  -->
  <div class="mat-sort-header-content">
    <ng-content></ng-content>
  </div>

  <!-- Disable animations while a current animation is running -->
  @if (_renderArrow()) {
    <div class="mat-sort-header-arrow">
      <ng-content select="[matSortHeaderIcon]">
        <svg viewBox="0 -960 960 960" focusable="false" aria-hidden="true">
          <path d="M440-240v-368L296-464l-56-56 240-240 240 240-56 56-144-144v368h-80Z"/>
        </svg>
      </ng-content>
    </div>
  }
</div>
`,
      styles: [".mat-sort-header {\n  cursor: pointer;\n}\n\n.mat-sort-header-disabled {\n  cursor: default;\n}\n\n.mat-sort-header-container {\n  display: flex;\n  align-items: center;\n  letter-spacing: normal;\n  outline: 0;\n}\n[mat-sort-header].cdk-keyboard-focused .mat-sort-header-container, [mat-sort-header].cdk-program-focused .mat-sort-header-container {\n  border-bottom: solid 1px currentColor;\n}\n.mat-sort-header-container::before {\n  margin: calc(calc(var(--mat-focus-indicator-border-width, 3px) + 2px) * -1);\n}\n\n.mat-sort-header-content {\n  display: flex;\n  align-items: center;\n}\n\n.mat-sort-header-position-before {\n  flex-direction: row-reverse;\n}\n\n@keyframes _mat-sort-header-recently-cleared-ascending {\n  from {\n    transform: translateY(0);\n    opacity: 1;\n  }\n  to {\n    transform: translateY(-25%);\n    opacity: 0;\n  }\n}\n@keyframes _mat-sort-header-recently-cleared-descending {\n  from {\n    transform: translateY(0) rotate(180deg);\n    opacity: 1;\n  }\n  to {\n    transform: translateY(25%) rotate(180deg);\n    opacity: 0;\n  }\n}\n.mat-sort-header-arrow {\n  height: 12px;\n  width: 12px;\n  position: relative;\n  transition: transform 225ms cubic-bezier(0.4, 0, 0.2, 1), opacity 225ms cubic-bezier(0.4, 0, 0.2, 1);\n  opacity: 0;\n  overflow: visible;\n  color: var(--mat-sort-arrow-color, var(--mat-sys-on-surface));\n}\n.mat-sort-header.cdk-keyboard-focused .mat-sort-header-arrow, .mat-sort-header.cdk-program-focused .mat-sort-header-arrow, .mat-sort-header:hover .mat-sort-header-arrow {\n  opacity: 0.54;\n}\n.mat-sort-header .mat-sort-header-sorted .mat-sort-header-arrow {\n  opacity: 1;\n}\n.mat-sort-header-descending .mat-sort-header-arrow {\n  transform: rotate(180deg);\n}\n.mat-sort-header-recently-cleared-ascending .mat-sort-header-arrow {\n  transform: translateY(-25%);\n}\n.mat-sort-header-recently-cleared-ascending .mat-sort-header-arrow {\n  transition: none;\n  animation: _mat-sort-header-recently-cleared-ascending 225ms cubic-bezier(0.4, 0, 0.2, 1) forwards;\n}\n.mat-sort-header-recently-cleared-descending .mat-sort-header-arrow {\n  transition: none;\n  animation: _mat-sort-header-recently-cleared-descending 225ms cubic-bezier(0.4, 0, 0.2, 1) forwards;\n}\n.mat-sort-header-animations-disabled .mat-sort-header-arrow {\n  transition-duration: 0ms;\n  animation-duration: 0ms;\n}\n.mat-sort-header-arrow > svg, .mat-sort-header-arrow [matSortHeaderIcon] {\n  width: 24px;\n  height: 24px;\n  fill: currentColor;\n  position: absolute;\n  top: 50%;\n  left: 50%;\n  margin: -12px 0 0 -12px;\n  transform: translateZ(0);\n}\n.mat-sort-header-arrow, [dir=rtl] .mat-sort-header-position-before .mat-sort-header-arrow {\n  margin: 0 0 0 6px;\n}\n.mat-sort-header-position-before .mat-sort-header-arrow, [dir=rtl] .mat-sort-header-arrow {\n  margin: 0 6px 0 0;\n}\n"]
    }]
  }], () => [], {
    id: [{
      type: Input,
      args: ["mat-sort-header"]
    }],
    arrowPosition: [{
      type: Input
    }],
    start: [{
      type: Input
    }],
    disabled: [{
      type: Input,
      args: [{
        transform: booleanAttribute
      }]
    }],
    sortActionDescription: [{
      type: Input
    }],
    disableClear: [{
      type: Input,
      args: [{
        transform: booleanAttribute
      }]
    }]
  });
})();
var MatSortModule = class _MatSortModule {
  static ɵfac = function MatSortModule_Factory(__ngFactoryType__) {
    return new (__ngFactoryType__ || _MatSortModule)();
  };
  static ɵmod = ɵɵdefineNgModule({
    type: _MatSortModule,
    imports: [MatSort, MatSortHeader],
    exports: [MatSort, MatSortHeader, BidiModule]
  });
  static ɵinj = ɵɵdefineInjector({
    imports: [BidiModule]
  });
};
(() => {
  (typeof ngDevMode === "undefined" || ngDevMode) && setClassMetadata(MatSortModule, [{
    type: NgModule,
    args: [{
      imports: [MatSort, MatSortHeader],
      exports: [MatSort, MatSortHeader, BidiModule]
    }]
  }], null, null);
})();
var MatSortHeaderIntl = class _MatSortHeaderIntl {
  changes = new Subject();
  static ɵfac = function MatSortHeaderIntl_Factory(__ngFactoryType__) {
    return new (__ngFactoryType__ || _MatSortHeaderIntl)();
  };
  static ɵprov = ɵɵdefineInjectable({
    token: _MatSortHeaderIntl,
    factory: _MatSortHeaderIntl.ɵfac,
    providedIn: "root"
  });
};
(() => {
  (typeof ngDevMode === "undefined" || ngDevMode) && setClassMetadata(MatSortHeaderIntl, [{
    type: Injectable,
    args: [{
      providedIn: "root"
    }]
  }], null, null);
})();
export {
  MAT_SORT_DEFAULT_OPTIONS,
  MatSort,
  MatSortHeader,
  MatSortHeaderIntl,
  MatSortModule
};
//# sourceMappingURL=@angular_material_sort.js.map
