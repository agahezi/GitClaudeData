# React 19 Component Examples

Read when writing a reusable React component and a complete fluid example would help.

## Example: fluid card list with Tailwind v4

```jsx
export function CardList({ items, minCard = '18rem' }) {
  return (
    <ul className="grid-auto-fit gap-fluid-md" style={{ '--grid-min': minCard }}>
      {items.map((item) => (
        <li key={item.id} className="@container/card">
          <article className="grid h-full gap-fluid-sm rounded-2xl bg-white p-[clamp(1rem,4cqi,2rem)] ring-1 ring-slate-200 @md/card:grid-cols-[auto_1fr]">
            <img src={item.image} alt="" className="aspect-video w-full rounded-xl object-cover @md/card:w-[clamp(6rem,30cqi,12rem)]" />
            <div className="min-w-0">
              <h3 className="text-[clamp(1.125rem,0.9rem+3cqi,1.75rem)] font-bold text-balance">{item.title}</h3>
              <p className="mt-fluid-xs text-fluid-base text-pretty">{item.text}</p>
              <div className="mt-fluid-sm flex flex-wrap gap-fluid-xs">
                <a href={item.href} className="touch-target inline-flex flex-[1_1_8rem] items-center justify-center rounded-xl bg-sky-600 px-fluid-sm font-bold text-white">
                  Open
                </a>
              </div>
            </div>
          </article>
        </li>
      ))}
    </ul>
  );
}
```

## Example: same component with CSS Modules (no Tailwind)

```jsx
import styles from './CardList.module.css';

export function CardList({ items, minCard = '18rem' }) {
  return (
    <ul className={`grid-auto-fit ${styles.list}`} style={{ '--grid-min': minCard }}>
      {items.map((item) => (
        <li key={item.id} className={styles.host}>
          <article className={styles.card}>
            <img src={item.image} alt="" className={styles.media} />
            <div className={styles.body}>
              <h3 className={styles.title}>{item.title}</h3>
              <p className={styles.text}>{item.text}</p>
              <div className={styles.actions}>
                <a href={item.href} className={styles.button}>Open</a>
              </div>
            </div>
          </article>
        </li>
      ))}
    </ul>
  );
}
```

```css
/* CardList.module.css */
.list { list-style: none; padding: 0; }
.host { container: card / inline-size; }
.card {
  display: grid;
  gap: var(--spacing-fluid-sm);
  block-size: 100%;
  padding: clamp(1rem, 4cqi, 2rem);
  border-radius: 1rem;
  background: white;
  box-shadow: 0 0 0 1px rgb(226 232 240);
}
.media { inline-size: 100%; aspect-ratio: 16 / 9; object-fit: cover; border-radius: 0.75rem; }
.body { min-inline-size: 0; }
.title { font-size: clamp(1.125rem, 0.9rem + 3cqi, 1.75rem); font-weight: 700; text-wrap: balance; }
.text { margin-block-start: var(--spacing-fluid-xs); font-size: var(--text-fluid-base); text-wrap: pretty; }
.actions { display: flex; flex-wrap: wrap; gap: var(--spacing-fluid-xs); margin-block-start: var(--spacing-fluid-sm); }
.button {
  flex: 1 1 8rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-block-size: var(--spacing-touch);
  padding-inline: var(--spacing-fluid-sm);
  border-radius: 0.75rem;
  background: rgb(2 132 199);
  color: white;
  font-weight: 700;
}

@container card (min-width: 28rem) {
  .card { grid-template-columns: auto 1fr; }
  .media { inline-size: clamp(6rem, 30cqi, 12rem); }
}
```

TypeScript note: custom properties in `style` need a cast, e.g. `style={{ '--grid-min': minCard } as React.CSSProperties}`.
