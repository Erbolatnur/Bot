import './globals.css';
import type { Metadata } from 'next';
export const metadata: Metadata = { title: 'CS2 DEMO HUB', description: 'Steam и FACEIT демки, статистика и повторы матчей CS2' };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="ru"><body>{children}</body></html>; }
