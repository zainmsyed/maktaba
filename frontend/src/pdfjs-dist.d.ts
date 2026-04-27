declare module 'pdfjs-dist/build/pdf.mjs' {
  export const GlobalWorkerOptions: { workerSrc: string };
  export function getDocument(options: { url: string }): { promise: Promise<any> };
}

declare module 'pdfjs-dist/build/pdf.worker.min.mjs?url' {
  const workerUrl: string;
  export default workerUrl;
}

declare module 'pdfjs-dist/web/pdf_viewer.mjs' {
  export class TextLayerBuilder {
    constructor(options: {
      pdfPage: any;
      onAppend?: (div: HTMLDivElement) => void;
    });
    div: HTMLDivElement;
    render(options: { viewport: any; images: any }): Promise<void>;
    cancel(): void;
    hide(): void;
    show(): void;
  }
}
