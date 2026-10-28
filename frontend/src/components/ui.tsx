import type { ButtonHTMLAttributes, ReactNode } from 'react';

export function Button(props: ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button type="button" {...props} className={`button ${props.className ?? ''}`} />;
}

export function Badge({ children, tone = 'neutral' }: {
  children: ReactNode; tone?: 'neutral' | 'accent' | 'warning';
}) {
  return <span className={`badge badge--${tone}`}>{children}</span>;
}

export function Panel({ title, children, className = '' }: {
  title: string; children: ReactNode; className?: string;
}) {
  return <section className={`panel ${className}`}><h2>{title}</h2>{children}</section>;
}

export function EmptyState({ title, children }: { title: string; children: ReactNode }) {
  return <div className="empty-state"><span className="empty-mark" aria-hidden="true">+</span>
    <h2>{title}</h2><p>{children}</p></div>;
}
