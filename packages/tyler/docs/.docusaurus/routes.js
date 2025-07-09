import React from 'react';
import ComponentCreator from '@docusaurus/ComponentCreator';

export default [
  {
    path: '/tyler/__docusaurus/debug',
    component: ComponentCreator('/tyler/__docusaurus/debug', '654'),
    exact: true
  },
  {
    path: '/tyler/__docusaurus/debug/config',
    component: ComponentCreator('/tyler/__docusaurus/debug/config', '538'),
    exact: true
  },
  {
    path: '/tyler/__docusaurus/debug/content',
    component: ComponentCreator('/tyler/__docusaurus/debug/content', '858'),
    exact: true
  },
  {
    path: '/tyler/__docusaurus/debug/globalData',
    component: ComponentCreator('/tyler/__docusaurus/debug/globalData', '492'),
    exact: true
  },
  {
    path: '/tyler/__docusaurus/debug/metadata',
    component: ComponentCreator('/tyler/__docusaurus/debug/metadata', '2bb'),
    exact: true
  },
  {
    path: '/tyler/__docusaurus/debug/registry',
    component: ComponentCreator('/tyler/__docusaurus/debug/registry', '102'),
    exact: true
  },
  {
    path: '/tyler/__docusaurus/debug/routes',
    component: ComponentCreator('/tyler/__docusaurus/debug/routes', '607'),
    exact: true
  },
  {
    path: '/tyler/markdown-page',
    component: ComponentCreator('/tyler/markdown-page', '8f1'),
    exact: true
  },
  {
    path: '/tyler/search',
    component: ComponentCreator('/tyler/search', 'f5c'),
    exact: true
  },
  {
    path: '/tyler/',
    component: ComponentCreator('/tyler/', '0cc'),
    routes: [
      {
        path: '/tyler/',
        component: ComponentCreator('/tyler/', 'e88'),
        routes: [
          {
            path: '/tyler/',
            component: ComponentCreator('/tyler/', 'd51'),
            routes: [
              {
                path: '/tyler/api-reference/',
                component: ComponentCreator('/tyler/api-reference/', '805'),
                exact: true
              },
              {
                path: '/tyler/api-reference/agent',
                component: ComponentCreator('/tyler/api-reference/agent', '16a'),
                exact: true,
                sidebar: "referenceSidebar"
              },
              {
                path: '/tyler/api-reference/attachment',
                component: ComponentCreator('/tyler/api-reference/attachment', '751'),
                exact: true,
                sidebar: "referenceSidebar"
              },
              {
                path: '/tyler/api-reference/file-store',
                component: ComponentCreator('/tyler/api-reference/file-store', 'a3d'),
                exact: true,
                sidebar: "referenceSidebar"
              },
              {
                path: '/tyler/api-reference/mcp',
                component: ComponentCreator('/tyler/api-reference/mcp', '746'),
                exact: true,
                sidebar: "referenceSidebar"
              },
              {
                path: '/tyler/api-reference/message',
                component: ComponentCreator('/tyler/api-reference/message', 'b1c'),
                exact: true,
                sidebar: "referenceSidebar"
              },
              {
                path: '/tyler/api-reference/registry',
                component: ComponentCreator('/tyler/api-reference/registry', '05b'),
                exact: true
              },
              {
                path: '/tyler/api-reference/thread',
                component: ComponentCreator('/tyler/api-reference/thread', 'f1e'),
                exact: true,
                sidebar: "referenceSidebar"
              },
              {
                path: '/tyler/api-reference/thread-store',
                component: ComponentCreator('/tyler/api-reference/thread-store', 'a07'),
                exact: true,
                sidebar: "referenceSidebar"
              },
              {
                path: '/tyler/built-in-tools',
                component: ComponentCreator('/tyler/built-in-tools', 'f5a'),
                exact: true
              },
              {
                path: '/tyler/category/api-reference',
                component: ComponentCreator('/tyler/category/api-reference', 'c3a'),
                exact: true
              },
              {
                path: '/tyler/category/examples',
                component: ComponentCreator('/tyler/category/examples', '576'),
                exact: true
              },
              {
                path: '/tyler/chat-with-tyler',
                component: ComponentCreator('/tyler/chat-with-tyler', '3ca'),
                exact: true,
                sidebar: "documentationSidebar"
              },
              {
                path: '/tyler/configuration',
                component: ComponentCreator('/tyler/configuration', 'cdb'),
                exact: true,
                sidebar: "referenceSidebar"
              },
              {
                path: '/tyler/core-concepts',
                component: ComponentCreator('/tyler/core-concepts', '7f8'),
                exact: true,
                sidebar: "documentationSidebar"
              },
              {
                path: '/tyler/examples/',
                component: ComponentCreator('/tyler/examples/', 'c04'),
                exact: true
              },
              {
                path: '/tyler/examples/database-storage',
                component: ComponentCreator('/tyler/examples/database-storage', '38f'),
                exact: true,
                sidebar: "documentationSidebar"
              },
              {
                path: '/tyler/examples/file-storage',
                component: ComponentCreator('/tyler/examples/file-storage', '6eb'),
                exact: true,
                sidebar: "documentationSidebar"
              },
              {
                path: '/tyler/examples/full-configuration',
                component: ComponentCreator('/tyler/examples/full-configuration', '640'),
                exact: true,
                sidebar: "documentationSidebar"
              },
              {
                path: '/tyler/examples/interrupt-tools',
                component: ComponentCreator('/tyler/examples/interrupt-tools', '476'),
                exact: true,
                sidebar: "documentationSidebar"
              },
              {
                path: '/tyler/examples/message-attachments',
                component: ComponentCreator('/tyler/examples/message-attachments', '5bd'),
                exact: true,
                sidebar: "documentationSidebar"
              },
              {
                path: '/tyler/examples/streaming',
                component: ComponentCreator('/tyler/examples/streaming', '966'),
                exact: true,
                sidebar: "documentationSidebar"
              },
              {
                path: '/tyler/examples/tools-streaming',
                component: ComponentCreator('/tyler/examples/tools-streaming', '293'),
                exact: true,
                sidebar: "documentationSidebar"
              },
              {
                path: '/tyler/examples/using-tools',
                component: ComponentCreator('/tyler/examples/using-tools', '7bc'),
                exact: true,
                sidebar: "documentationSidebar"
              },
              {
                path: '/tyler/how-it-works',
                component: ComponentCreator('/tyler/how-it-works', '39c'),
                exact: true,
                sidebar: "documentationSidebar"
              },
              {
                path: '/tyler/installation',
                component: ComponentCreator('/tyler/installation', 'a51'),
                exact: true
              },
              {
                path: '/tyler/quickstart',
                component: ComponentCreator('/tyler/quickstart', '770'),
                exact: true,
                sidebar: "documentationSidebar"
              },
              {
                path: '/tyler/tools/audio',
                component: ComponentCreator('/tyler/tools/audio', '3c2'),
                exact: true,
                sidebar: "documentationSidebar"
              },
              {
                path: '/tyler/tools/command-line',
                component: ComponentCreator('/tyler/tools/command-line', '6fb'),
                exact: true,
                sidebar: "documentationSidebar"
              },
              {
                path: '/tyler/tools/files',
                component: ComponentCreator('/tyler/tools/files', 'cfe'),
                exact: true,
                sidebar: "documentationSidebar"
              },
              {
                path: '/tyler/tools/image',
                component: ComponentCreator('/tyler/tools/image', '40e'),
                exact: true,
                sidebar: "documentationSidebar"
              },
              {
                path: '/tyler/tools/mcp',
                component: ComponentCreator('/tyler/tools/mcp', '73a'),
                exact: true,
                sidebar: "documentationSidebar"
              },
              {
                path: '/tyler/tools/notion',
                component: ComponentCreator('/tyler/tools/notion', '839'),
                exact: true,
                sidebar: "documentationSidebar"
              },
              {
                path: '/tyler/tools/overview',
                component: ComponentCreator('/tyler/tools/overview', 'e90'),
                exact: true,
                sidebar: "documentationSidebar"
              },
              {
                path: '/tyler/tools/slack',
                component: ComponentCreator('/tyler/tools/slack', 'e04'),
                exact: true,
                sidebar: "documentationSidebar"
              },
              {
                path: '/tyler/tools/web',
                component: ComponentCreator('/tyler/tools/web', 'ab2'),
                exact: true,
                sidebar: "documentationSidebar"
              },
              {
                path: '/tyler/troubleshooting',
                component: ComponentCreator('/tyler/troubleshooting', '43d'),
                exact: true,
                sidebar: "referenceSidebar"
              },
              {
                path: '/tyler/',
                component: ComponentCreator('/tyler/', '060'),
                exact: true,
                sidebar: "documentationSidebar"
              }
            ]
          }
        ]
      }
    ]
  },
  {
    path: '*',
    component: ComponentCreator('*'),
  },
];
