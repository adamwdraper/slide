import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

/**
 * Creating a sidebar enables you to:
 - create an ordered group of docs
 - render a sidebar for each doc of that group
 - provide next/previous navigation

 The sidebars can be generated from the filesystem, or explicitly defined here.

 Create as many sidebars as you want.
 */
const sidebars: SidebarsConfig = {
  // Documentation sidebar
  documentationSidebar: [
    {
      type: 'category',
      label: 'Get started',
      className: 'category-no-arrow',
      collapsed: false,
      collapsible: false,
      items: [
        'intro',
        'quickstart',
        'how-it-works',
        'chat-with-tyler',
      ],
    },
    {
      type: 'category',
      label: 'Components',
      className: 'category-no-arrow',
      collapsed: false,
      collapsible: false,
      items: [
        'core-concepts',
      ],
    },
    {
      type: 'category',
      label: 'Tools',
      className: 'category-no-arrow',
      collapsed: false,
      collapsible: false,
      items: [
        'tools/overview',
        'tools/web',
        'tools/slack',
        'tools/notion',
        'tools/image',
        'tools/command-line',
        'tools/audio',
        'tools/files',
        'tools/mcp',
      ],
    },
    {
      type: 'category',
      label: 'Guides',
      className: 'category-no-arrow',
      collapsed: false,
      collapsible: false,
      items: [
        'examples/using-tools',
        'examples/tools-streaming',
        'examples/streaming',
        'examples/database-storage',
        'examples/file-storage',
        'examples/message-attachments',
        'examples/interrupt-tools',
        'examples/full-configuration',
      ],
    },
  ],

  // Reference sidebar
  referenceSidebar: [
    {
      type: 'category',
      label: 'Guides',
      className: 'category-no-arrow',
      collapsed: false,
      collapsible: false,
      items: [
        'configuration',
        'troubleshooting',
      ],
    },
    {
      type: 'category',
      label: 'API Reference',
      className: 'category-no-arrow',
      collapsed: false,
      collapsible: false,
      items: [
        'api-reference/agent',
        'api-reference/thread',
        'api-reference/message',
        'api-reference/attachment',
        'api-reference/file-store',
        'api-reference/thread-store',
        'api-reference/mcp'
      ],
    },
  ],
};

export default sidebars;
