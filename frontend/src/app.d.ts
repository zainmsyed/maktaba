/// <reference types="@sveltejs/kit" />

declare global {
  namespace App {
    interface PageData {
      apiUrl: string;
    }
  }
}

export {};
