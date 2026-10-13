import type { ReactNode } from 'react';
import { Card } from '../../components/Card.tsx';

export function AuthLayout({
  subtitle,
  children,
}: {
  subtitle: string;
  children: ReactNode;
}) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-primary-50/40 px-4 py-12">
      <div className="w-full max-w-sm">
        <h1 className="text-center font-display text-2xl font-semibold tracking-tight text-primary-600">
          Medvault
        </h1>
        <p className="mt-2 text-center text-sm text-ink-600">{subtitle}</p>
        <Card className="mt-8 p-6">{children}</Card>
      </div>
    </main>
  );
}
