// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
	site: 'https://gpui-docs.vercel.app',
	integrations: [
		starlight({
			title: 'GPUI',
			description: 'Learn GPUI, the GPU-accelerated Rust UI framework behind the Zed editor. Unofficial, beginner-friendly documentation.',
			logo: { src: './src/assets/logo.svg' },
			favicon: '/favicon.svg',
			customCss: ['./src/styles/custom.css'],
			head: [
				{ tag: 'link', attrs: { rel: 'preconnect', href: 'https://fonts.googleapis.com' } },
				{ tag: 'link', attrs: { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: '' } },
				{ tag: 'link', attrs: { rel: 'stylesheet', href: 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap' } },
			],
			social: [
				{ icon: 'github', label: 'GitHub', href: 'https://github.com/ugochukwu-850/gpui-docs' },
			],
			editLink: { baseUrl: 'https://github.com/ugochukwu-850/gpui-docs/edit/main/' },
			credits: false,
			expressiveCode: {
				themes: ['github-dark-dimmed', 'github-light'],
				styleOverrides: { borderRadius: '0.6rem', codeFontFamily: "'JetBrains Mono', ui-monospace, monospace", codeFontSize: '0.86rem' },
			},
			sidebar: [
				{ label: 'Start Here', items: [{ autogenerate: { directory: 'start' } }] },
				{ label: 'Tutorials', items: [{ autogenerate: { directory: 'tutorials' } }] },
				{ label: 'Guides', items: [{ autogenerate: { directory: 'guides' } }] },
				{ label: 'Deep Dive', collapsed: true, items: [{ autogenerate: { directory: 'deep-dive' } }] },
				{ label: 'Codebase Tour', collapsed: true, items: [{ autogenerate: { directory: 'codebase' } }] },
				{ label: 'Reference', collapsed: true, items: [{ autogenerate: { directory: 'reference' } }] },
			],
		}),
	],
});
