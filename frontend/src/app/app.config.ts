import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { ApplicationConfig, inject, provideAppInitializer, provideBrowserGlobalErrorListeners } from '@angular/core';
import { MAT_FORM_FIELD_DEFAULT_OPTIONS } from '@angular/material/form-field';
import { TitleStrategy, provideRouter, withComponentInputBinding, withInMemoryScrolling } from '@angular/router';

import { routes } from './app.routes';
import { AuthService } from './core/auth/auth.service';
import { authInterceptor, errorInterceptor } from './core/http/interceptors';
import { AppTitleStrategy } from './core/title.strategy';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes, withComponentInputBinding(), withInMemoryScrolling({ scrollPositionRestoration: 'top' })),
    // errorInterceptor is outermost so it sees the final result after the auth refresh-and-retry.
    provideHttpClient(withInterceptors([errorInterceptor, authInterceptor])),
    // Restore the session from the httpOnly refresh cookie before the first navigation.
    provideAppInitializer(() => inject(AuthService).restoreSession()),
    { provide: TitleStrategy, useClass: AppTitleStrategy },
    { provide: MAT_FORM_FIELD_DEFAULT_OPTIONS, useValue: { appearance: 'outline' } },
  ],
};
