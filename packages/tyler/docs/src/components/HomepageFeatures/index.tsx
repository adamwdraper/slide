import type {ReactNode} from 'react';
import clsx from 'clsx';
import Heading from '@theme/Heading';
import styles from './styles.module.css';

type FeatureItem = {
  title: string;
  description: ReactNode;
};

const FeatureList: FeatureItem[] = [
  {
    title: 'Multimodal Support',
    description: (
      <>
        Process and understand images, audio, PDFs, and more out of the box. Built-in support for handling various file types with automatic content extraction.
      </>
    ),
  },
  {
    title: 'Ready-to-Use Tools',
    description: (
      <>
        Comprehensive set of built-in tools for common tasks, with easy integration of custom capabilities. Connect with services like Slack and Notion seamlessly.
      </>
    ),
  },
  {
    title: 'Structured Data Model',
    description: (
      <>
        Built-in support for threads, messages, and attachments to maintain conversation context. Choose between in-memory, SQLite, or PostgreSQL for persistence.
      </>
    ),
  },
];

function Feature({title, description}: FeatureItem) {
  return (
    <div className={clsx('col col--4')}>
      <div className={clsx('text--center padding-horiz--md', styles.featureItem)}>
        <Heading as="h3">{title}</Heading>
        <p>{description}</p>
      </div>
    </div>
  );
}

export default function HomepageFeatures(): ReactNode {
  return (
    <>
      <section className={clsx(styles.features, styles.demoSection)}>
        <div className="container">
          <div className={clsx('text--center')}>
            <div className={styles.demoContainer}>
              <img 
                src="img/tyler_chat_UI_demo_short.gif" 
                alt="Tyler Chat UI Demo"
                className={styles.demoGif}
              />
            </div>
          </div>
        </div>
      </section>

      <section className={styles.features}>
        <div className={clsx('container', styles.featuresContainer)}>
          <div className="row">
            {FeatureList.map((props, idx) => (
              <Feature key={idx} {...props} />
            ))}
          </div>
        </div>
      </section>
    </>
  );
}
