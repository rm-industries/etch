import { registerPreviewTemplate, type CustomPreviewTemplateProps } from '@sveltia/cms';

import { previewCollectionNames } from './preview-collections';

const renderDocPreview = ({ document, widgetFor }: CustomPreviewTemplateProps) => {
  document.body.classList.add('prose', 'mx-auto');

  return widgetFor('body');
};

export const registerSveltiaPreviews = (register = registerPreviewTemplate) => {
  for (const name of previewCollectionNames) register(name, renderDocPreview);
};
