import {
  A11yModule,
  AriaDescriber,
  InteractivityChecker,
  _IdGenerator
} from "./chunk-7FBJIU3R.js";
import "./chunk-XA6252L2.js";
import {
  _VisuallyHiddenLoader
} from "./chunk-6OTIV4AS.js";
import "./chunk-V5JFTKFM.js";
import {
  _animationsDisabled
} from "./chunk-BKYXKDCC.js";
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
  Component,
  Directive,
  ElementRef,
  Input,
  NgModule,
  Renderer2,
  ViewEncapsulation,
  booleanAttribute,
  setClassMetadata,
  ɵɵclassProp,
  ɵɵdefineComponent,
  ɵɵdefineDirective,
  ɵɵdefineNgModule
} from "./chunk-N5ZPR4X7.js";
import {
  DOCUMENT,
  NgZone,
  inject,
  ɵɵdefineInjector
} from "./chunk-UNRALM3K.js";
import "./chunk-RSS3ODKE.js";
import "./chunk-75NUGXPU.js";

// node_modules/@angular/material/fesm2022/badge.mjs
var BADGE_CONTENT_CLASS = "mat-badge-content";
var _MatBadgeStyleLoader = class __MatBadgeStyleLoader {
  static ɵfac = function _MatBadgeStyleLoader_Factory(__ngFactoryType__) {
    return new (__ngFactoryType__ || __MatBadgeStyleLoader)();
  };
  static ɵcmp = ɵɵdefineComponent({
    type: __MatBadgeStyleLoader,
    selectors: [["ng-component"]],
    decls: 0,
    vars: 0,
    template: function _MatBadgeStyleLoader_Template(rf, ctx) {
    },
    styles: [".mat-badge {\n  position: relative;\n}\n.mat-badge.mat-badge {\n  overflow: visible;\n}\n\n.mat-badge-content {\n  position: absolute;\n  text-align: center;\n  display: inline-block;\n  transition: transform 200ms ease-in-out;\n  transform: scale(0.6);\n  overflow: hidden;\n  white-space: nowrap;\n  text-overflow: ellipsis;\n  box-sizing: border-box;\n  pointer-events: none;\n  background-color: var(--mat-badge-background-color, var(--mat-sys-error));\n  color: var(--mat-badge-text-color, var(--mat-sys-on-error));\n  font-family: var(--mat-badge-text-font, var(--mat-sys-label-small-font));\n  font-weight: var(--mat-badge-text-weight, var(--mat-sys-label-small-weight));\n  border-radius: var(--mat-badge-container-shape, var(--mat-sys-corner-full));\n}\n.mat-badge-above .mat-badge-content {\n  bottom: 100%;\n}\n.mat-badge-below .mat-badge-content {\n  top: 100%;\n}\n.mat-badge-before .mat-badge-content {\n  right: 100%;\n}\n[dir=rtl] .mat-badge-before .mat-badge-content {\n  right: auto;\n  left: 100%;\n}\n.mat-badge-after .mat-badge-content {\n  left: 100%;\n}\n[dir=rtl] .mat-badge-after .mat-badge-content {\n  left: auto;\n  right: 100%;\n}\n@media (forced-colors: active) {\n  .mat-badge-content {\n    outline: solid 1px;\n    border-radius: 0;\n  }\n}\n\n.mat-badge-disabled .mat-badge-content {\n  background-color: var(--mat-badge-disabled-state-background-color, color-mix(in srgb, var(--mat-sys-error) 38%, transparent));\n  color: var(--mat-badge-disabled-state-text-color, var(--mat-sys-on-error));\n}\n\n.mat-badge-hidden .mat-badge-content {\n  display: none;\n}\n\n.ng-animate-disabled .mat-badge-content,\n.mat-badge-content._mat-animation-noopable {\n  transition: none;\n}\n\n.mat-badge-content.mat-badge-active {\n  transform: none;\n}\n\n.mat-badge-small .mat-badge-content {\n  width: var(--mat-badge-legacy-small-size-container-size, unset);\n  height: var(--mat-badge-legacy-small-size-container-size, unset);\n  min-width: var(--mat-badge-small-size-container-size, 6px);\n  min-height: var(--mat-badge-small-size-container-size, 6px);\n  line-height: var(--mat-badge-small-size-line-height, 6px);\n  padding: var(--mat-badge-small-size-container-padding, 0);\n  font-size: var(--mat-badge-small-size-text-size, 0);\n  margin: var(--mat-badge-small-size-container-offset, -6px 0);\n}\n.mat-badge-small.mat-badge-overlap .mat-badge-content {\n  margin: var(--mat-badge-small-size-container-overlap-offset, -6px);\n}\n\n.mat-badge-medium .mat-badge-content {\n  width: var(--mat-badge-legacy-container-size, unset);\n  height: var(--mat-badge-legacy-container-size, unset);\n  min-width: var(--mat-badge-container-size, 16px);\n  min-height: var(--mat-badge-container-size, 16px);\n  line-height: var(--mat-badge-line-height, 16px);\n  padding: var(--mat-badge-container-padding, 0 4px);\n  font-size: var(--mat-badge-text-size, var(--mat-sys-label-small-size));\n  margin: var(--mat-badge-container-offset, -12px 0);\n}\n.mat-badge-medium.mat-badge-overlap .mat-badge-content {\n  margin: var(--mat-badge-container-overlap-offset, -12px);\n}\n\n.mat-badge-large .mat-badge-content {\n  width: var(--mat-badge-legacy-large-size-container-size, unset);\n  height: var(--mat-badge-legacy-large-size-container-size, unset);\n  min-width: var(--mat-badge-large-size-container-size, 16px);\n  min-height: var(--mat-badge-large-size-container-size, 16px);\n  line-height: var(--mat-badge-large-size-line-height, 16px);\n  padding: var(--mat-badge-large-size-container-padding, 0 4px);\n  font-size: var(--mat-badge-large-size-text-size, var(--mat-sys-label-small-size));\n  margin: var(--mat-badge-large-size-container-offset, -12px 0);\n}\n.mat-badge-large.mat-badge-overlap .mat-badge-content {\n  margin: var(--mat-badge-large-size-container-overlap-offset, -12px);\n}\n"],
    encapsulation: 2,
    changeDetection: 0
  });
};
(() => {
  (typeof ngDevMode === "undefined" || ngDevMode) && setClassMetadata(_MatBadgeStyleLoader, [{
    type: Component,
    args: [{
      encapsulation: ViewEncapsulation.None,
      template: "",
      changeDetection: ChangeDetectionStrategy.OnPush,
      styles: [".mat-badge {\n  position: relative;\n}\n.mat-badge.mat-badge {\n  overflow: visible;\n}\n\n.mat-badge-content {\n  position: absolute;\n  text-align: center;\n  display: inline-block;\n  transition: transform 200ms ease-in-out;\n  transform: scale(0.6);\n  overflow: hidden;\n  white-space: nowrap;\n  text-overflow: ellipsis;\n  box-sizing: border-box;\n  pointer-events: none;\n  background-color: var(--mat-badge-background-color, var(--mat-sys-error));\n  color: var(--mat-badge-text-color, var(--mat-sys-on-error));\n  font-family: var(--mat-badge-text-font, var(--mat-sys-label-small-font));\n  font-weight: var(--mat-badge-text-weight, var(--mat-sys-label-small-weight));\n  border-radius: var(--mat-badge-container-shape, var(--mat-sys-corner-full));\n}\n.mat-badge-above .mat-badge-content {\n  bottom: 100%;\n}\n.mat-badge-below .mat-badge-content {\n  top: 100%;\n}\n.mat-badge-before .mat-badge-content {\n  right: 100%;\n}\n[dir=rtl] .mat-badge-before .mat-badge-content {\n  right: auto;\n  left: 100%;\n}\n.mat-badge-after .mat-badge-content {\n  left: 100%;\n}\n[dir=rtl] .mat-badge-after .mat-badge-content {\n  left: auto;\n  right: 100%;\n}\n@media (forced-colors: active) {\n  .mat-badge-content {\n    outline: solid 1px;\n    border-radius: 0;\n  }\n}\n\n.mat-badge-disabled .mat-badge-content {\n  background-color: var(--mat-badge-disabled-state-background-color, color-mix(in srgb, var(--mat-sys-error) 38%, transparent));\n  color: var(--mat-badge-disabled-state-text-color, var(--mat-sys-on-error));\n}\n\n.mat-badge-hidden .mat-badge-content {\n  display: none;\n}\n\n.ng-animate-disabled .mat-badge-content,\n.mat-badge-content._mat-animation-noopable {\n  transition: none;\n}\n\n.mat-badge-content.mat-badge-active {\n  transform: none;\n}\n\n.mat-badge-small .mat-badge-content {\n  width: var(--mat-badge-legacy-small-size-container-size, unset);\n  height: var(--mat-badge-legacy-small-size-container-size, unset);\n  min-width: var(--mat-badge-small-size-container-size, 6px);\n  min-height: var(--mat-badge-small-size-container-size, 6px);\n  line-height: var(--mat-badge-small-size-line-height, 6px);\n  padding: var(--mat-badge-small-size-container-padding, 0);\n  font-size: var(--mat-badge-small-size-text-size, 0);\n  margin: var(--mat-badge-small-size-container-offset, -6px 0);\n}\n.mat-badge-small.mat-badge-overlap .mat-badge-content {\n  margin: var(--mat-badge-small-size-container-overlap-offset, -6px);\n}\n\n.mat-badge-medium .mat-badge-content {\n  width: var(--mat-badge-legacy-container-size, unset);\n  height: var(--mat-badge-legacy-container-size, unset);\n  min-width: var(--mat-badge-container-size, 16px);\n  min-height: var(--mat-badge-container-size, 16px);\n  line-height: var(--mat-badge-line-height, 16px);\n  padding: var(--mat-badge-container-padding, 0 4px);\n  font-size: var(--mat-badge-text-size, var(--mat-sys-label-small-size));\n  margin: var(--mat-badge-container-offset, -12px 0);\n}\n.mat-badge-medium.mat-badge-overlap .mat-badge-content {\n  margin: var(--mat-badge-container-overlap-offset, -12px);\n}\n\n.mat-badge-large .mat-badge-content {\n  width: var(--mat-badge-legacy-large-size-container-size, unset);\n  height: var(--mat-badge-legacy-large-size-container-size, unset);\n  min-width: var(--mat-badge-large-size-container-size, 16px);\n  min-height: var(--mat-badge-large-size-container-size, 16px);\n  line-height: var(--mat-badge-large-size-line-height, 16px);\n  padding: var(--mat-badge-large-size-container-padding, 0 4px);\n  font-size: var(--mat-badge-large-size-text-size, var(--mat-sys-label-small-size));\n  margin: var(--mat-badge-large-size-container-offset, -12px 0);\n}\n.mat-badge-large.mat-badge-overlap .mat-badge-content {\n  margin: var(--mat-badge-large-size-container-overlap-offset, -12px);\n}\n"]
    }]
  }], null, null);
})();
var MatBadge = class _MatBadge {
  _ngZone = inject(NgZone);
  _elementRef = inject(ElementRef);
  _ariaDescriber = inject(AriaDescriber);
  _renderer = inject(Renderer2);
  _animationsDisabled = _animationsDisabled();
  _idGenerator = inject(_IdGenerator);
  get color() {
    return this._color;
  }
  set color(value) {
    this._setColor(value);
    this._color = value;
  }
  _color = "primary";
  overlap = true;
  disabled = false;
  position = "above after";
  get content() {
    return this._content;
  }
  set content(newContent) {
    this._updateRenderedContent(newContent);
  }
  _content;
  get description() {
    return this._description;
  }
  set description(newDescription) {
    this._updateDescription(newDescription);
  }
  _description;
  size = "medium";
  hidden = false;
  _badgeElement;
  _inlineBadgeDescription;
  _isInitialized = false;
  _interactivityChecker = inject(InteractivityChecker);
  _document = inject(DOCUMENT);
  constructor() {
    const styleLoader = inject(_CdkPrivateStyleLoader);
    styleLoader.load(_MatBadgeStyleLoader);
    styleLoader.load(_VisuallyHiddenLoader);
    if (typeof ngDevMode === "undefined" || ngDevMode) {
      const nativeElement = this._elementRef.nativeElement;
      if (nativeElement.nodeType !== nativeElement.ELEMENT_NODE) {
        throw Error("matBadge must be attached to an element node.");
      }
    }
  }
  isAbove() {
    return this.position.indexOf("below") === -1;
  }
  isAfter() {
    return this.position.indexOf("before") === -1;
  }
  getBadgeElement() {
    return this._badgeElement;
  }
  ngOnInit() {
    this._clearExistingBadges();
    if (this.content && !this._badgeElement) {
      this._badgeElement = this._createBadgeElement();
      this._updateRenderedContent(this.content);
    }
    this._isInitialized = true;
  }
  ngAfterViewInit() {
    if (typeof ngDevMode === "undefined" || ngDevMode) {
      const nativeElement = this._elementRef.nativeElement;
      if (nativeElement.tagName.toLowerCase() === "mat-icon" && nativeElement.getAttribute("aria-hidden") === "true") {
        console.warn(`Detected a matBadge on an "aria-hidden" "<mat-icon>". Consider setting aria-hidden="false" in order to surface the information assistive technology.
${nativeElement.outerHTML}`);
      }
    }
  }
  ngOnDestroy() {
    if (this._renderer.destroyNode) {
      this._renderer.destroyNode(this._badgeElement);
      this._inlineBadgeDescription?.remove();
    }
    this._ariaDescriber.removeDescription(this._elementRef.nativeElement, this.description);
  }
  _isHostInteractive() {
    return this._interactivityChecker.isFocusable(this._elementRef.nativeElement, {
      ignoreVisibility: true
    });
  }
  _createBadgeElement() {
    const badgeElement = this._renderer.createElement("span");
    const activeClass = "mat-badge-active";
    badgeElement.setAttribute("id", this._idGenerator.getId("mat-badge-content-"));
    badgeElement.setAttribute("aria-hidden", "true");
    badgeElement.classList.add(BADGE_CONTENT_CLASS);
    if (this._animationsDisabled) {
      badgeElement.classList.add("_mat-animation-noopable");
    }
    this._elementRef.nativeElement.appendChild(badgeElement);
    if (typeof requestAnimationFrame === "function" && !this._animationsDisabled) {
      this._ngZone.runOutsideAngular(() => {
        requestAnimationFrame(() => {
          badgeElement.classList.add(activeClass);
        });
      });
    } else {
      badgeElement.classList.add(activeClass);
    }
    return badgeElement;
  }
  _updateRenderedContent(newContent) {
    const newContentNormalized = `${newContent ?? ""}`.trim();
    if (this._isInitialized && newContentNormalized && !this._badgeElement) {
      this._badgeElement = this._createBadgeElement();
    }
    if (this._badgeElement) {
      this._badgeElement.textContent = newContentNormalized;
    }
    this._content = newContentNormalized;
  }
  _updateDescription(newDescription) {
    this._ariaDescriber.removeDescription(this._elementRef.nativeElement, this.description);
    if (!newDescription || this._isHostInteractive()) {
      this._removeInlineDescription();
    }
    this._description = newDescription;
    if (this._isHostInteractive()) {
      this._ariaDescriber.describe(this._elementRef.nativeElement, newDescription);
    } else {
      this._updateInlineDescription();
    }
  }
  _updateInlineDescription() {
    if (!this._inlineBadgeDescription) {
      this._inlineBadgeDescription = this._document.createElement("span");
      this._inlineBadgeDescription.classList.add("cdk-visually-hidden");
    }
    this._inlineBadgeDescription.textContent = this.description;
    this._badgeElement?.appendChild(this._inlineBadgeDescription);
  }
  _removeInlineDescription() {
    this._inlineBadgeDescription?.remove();
    this._inlineBadgeDescription = void 0;
  }
  _setColor(colorPalette) {
    const classList = this._elementRef.nativeElement.classList;
    classList.remove(`mat-badge-${this._color}`);
    if (colorPalette) {
      classList.add(`mat-badge-${colorPalette}`);
    }
  }
  _clearExistingBadges() {
    const badges = this._elementRef.nativeElement.querySelectorAll(`:scope > .${BADGE_CONTENT_CLASS}`);
    for (const badgeElement of Array.from(badges)) {
      if (badgeElement !== this._badgeElement) {
        badgeElement.remove();
      }
    }
  }
  static ɵfac = function MatBadge_Factory(__ngFactoryType__) {
    return new (__ngFactoryType__ || _MatBadge)();
  };
  static ɵdir = ɵɵdefineDirective({
    type: _MatBadge,
    selectors: [["", "matBadge", ""]],
    hostAttrs: [1, "mat-badge"],
    hostVars: 20,
    hostBindings: function MatBadge_HostBindings(rf, ctx) {
      if (rf & 2) {
        ɵɵclassProp("mat-badge-overlap", ctx.overlap)("mat-badge-above", ctx.isAbove())("mat-badge-below", !ctx.isAbove())("mat-badge-before", !ctx.isAfter())("mat-badge-after", ctx.isAfter())("mat-badge-small", ctx.size === "small")("mat-badge-medium", ctx.size === "medium")("mat-badge-large", ctx.size === "large")("mat-badge-hidden", ctx.hidden || !ctx.content)("mat-badge-disabled", ctx.disabled);
      }
    },
    inputs: {
      color: [0, "matBadgeColor", "color"],
      overlap: [2, "matBadgeOverlap", "overlap", booleanAttribute],
      disabled: [2, "matBadgeDisabled", "disabled", booleanAttribute],
      position: [0, "matBadgePosition", "position"],
      content: [0, "matBadge", "content"],
      description: [0, "matBadgeDescription", "description"],
      size: [0, "matBadgeSize", "size"],
      hidden: [2, "matBadgeHidden", "hidden", booleanAttribute]
    }
  });
};
(() => {
  (typeof ngDevMode === "undefined" || ngDevMode) && setClassMetadata(MatBadge, [{
    type: Directive,
    args: [{
      selector: "[matBadge]",
      host: {
        "class": "mat-badge",
        "[class.mat-badge-overlap]": "overlap",
        "[class.mat-badge-above]": "isAbove()",
        "[class.mat-badge-below]": "!isAbove()",
        "[class.mat-badge-before]": "!isAfter()",
        "[class.mat-badge-after]": "isAfter()",
        "[class.mat-badge-small]": 'size === "small"',
        "[class.mat-badge-medium]": 'size === "medium"',
        "[class.mat-badge-large]": 'size === "large"',
        "[class.mat-badge-hidden]": "hidden || !content",
        "[class.mat-badge-disabled]": "disabled"
      }
    }]
  }], () => [], {
    color: [{
      type: Input,
      args: ["matBadgeColor"]
    }],
    overlap: [{
      type: Input,
      args: [{
        alias: "matBadgeOverlap",
        transform: booleanAttribute
      }]
    }],
    disabled: [{
      type: Input,
      args: [{
        alias: "matBadgeDisabled",
        transform: booleanAttribute
      }]
    }],
    position: [{
      type: Input,
      args: ["matBadgePosition"]
    }],
    content: [{
      type: Input,
      args: ["matBadge"]
    }],
    description: [{
      type: Input,
      args: ["matBadgeDescription"]
    }],
    size: [{
      type: Input,
      args: ["matBadgeSize"]
    }],
    hidden: [{
      type: Input,
      args: [{
        alias: "matBadgeHidden",
        transform: booleanAttribute
      }]
    }]
  });
})();
var MatBadgeModule = class _MatBadgeModule {
  static ɵfac = function MatBadgeModule_Factory(__ngFactoryType__) {
    return new (__ngFactoryType__ || _MatBadgeModule)();
  };
  static ɵmod = ɵɵdefineNgModule({
    type: _MatBadgeModule,
    imports: [A11yModule, MatBadge, _MatBadgeStyleLoader],
    exports: [MatBadge, BidiModule]
  });
  static ɵinj = ɵɵdefineInjector({
    imports: [A11yModule, BidiModule]
  });
};
(() => {
  (typeof ngDevMode === "undefined" || ngDevMode) && setClassMetadata(MatBadgeModule, [{
    type: NgModule,
    args: [{
      imports: [A11yModule, MatBadge, _MatBadgeStyleLoader],
      exports: [MatBadge, BidiModule]
    }]
  }], null, null);
})();
export {
  MatBadge,
  MatBadgeModule
};
//# sourceMappingURL=@angular_material_badge.js.map
