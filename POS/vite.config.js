import path from "node:path";
import { promises as fs } from "node:fs";
import vue from "@vitejs/plugin-vue";
import frappeui from "frappe-ui/vite";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";
import { viteStaticCopy } from "vite-plugin-static-copy";

// Get build version from environment or use timestamp
const buildVersion = process.env.POS_NEXT_BUILD_VERSION || Date.now().toString();
const enableSourceMap = process.env.POS_NEXT_ENABLE_SOURCEMAP === "true";

/**
 * Vite plugin to write build version to version.json file
 * This enables cache busting and version tracking
 */
function posNextBuildVersionPlugin(version) {
	return {
		name: "pos-next-build-version",
		apply: "build",
		async writeBundle() {
			const versionFile = path.resolve(__dirname, "../pos_next/public/pos/version.json");
			await fs.mkdir(path.dirname(versionFile), { recursive: true });
			await fs.writeFile(
				versionFile,
				JSON.stringify(
					{
						version,
						timestamp: new Date().toISOString(),
						buildDate: new Date().toLocaleDateString("en-US", {
							year: "numeric",
							month: "long",
							day: "numeric",
						}),
					},
					null,
					2
				),
				"utf8"
			);
			console.log(`\n✓ Build version written: ${version}`);
		},
	};
}


/**
 * Generate a static POS application shell for offline navigation.
 * ERPNext's normal /pos page retains its server-rendered boot data.
 */
function posNextOfflineShellPlugin() {
    return {
        name: "pos-next-offline-shell",
        apply: "build",
        async writeBundle() {
            const outputDir = path.resolve(
                __dirname,
                "../pos_next/public/pos"
            );
            const sourceFile = path.join(outputDir, "index.html");
            const destinationFile = path.join(
                outputDir,
                "offline-shell.html"
            );

            let html = await fs.readFile(sourceFile, "utf8");

            const bootScript =
                /<script>\s*{%\s*for key in boot\s*%}[\s\S]*?{%\s*endfor\s*%}\s*<\/script>/g;

            const matches = html.match(bootScript) || [];

            if (matches.length !== 1) {
                throw new Error(
                    `Expected one Jinja boot script; found ${matches.length}`
                );
            }

            html = html.replace(bootScript, "");

            if (html.includes("{%") || html.includes("{{")) {
                throw new Error("Offline shell contains Jinja expressions");
            }

            await fs.writeFile(destinationFile, html, "utf8");
            console.log("POSNext offline application shell generated");
        },
    };
}

// https://vitejs.dev/config/
export default defineConfig({
	plugins: [
		posNextBuildVersionPlugin(buildVersion),
		posNextOfflineShellPlugin(),
		frappeui({
			frappeProxy: true,
			jinjaBootData: true,
			lucideIcons: true,
			buildConfig: {
				indexHtmlPath: "../pos_next/www/pos.html",
				outDir: "../pos_next/public/pos",
				emptyOutDir: true,
				sourcemap: enableSourceMap,
			},
		}),
		vue(),
		viteStaticCopy({
			targets: [
				{
					src: "src/workers",
					dest: ".",
				},
			],
		}),
		VitePWA({
			scope: "/pos",
			registerType: "autoUpdate",
			includeAssets: ["favicon.png", "icon.svg", "icon-maskable.svg"],
			manifest: {
				name: "POSNext",
				short_name: "POSNext",
				description:
					"Point of Sale system with real-time billing, stock management, and offline support",
				theme_color: "#4F46E5",
				background_color: "#ffffff",
				display: "standalone",
				scope: "/pos",
				start_url: "/pos",
				icons: [
					{
						src: "/assets/pos_next/pos/icon.svg",
						sizes: "192x192",
						type: "image/svg+xml",
						purpose: "any",
					},
					{
						src: "/assets/pos_next/pos/icon.svg",
						sizes: "512x512",
						type: "image/svg+xml",
						purpose: "any",
					},
					{
						src: "/assets/pos_next/pos/icon-maskable.svg",
						sizes: "192x192",
						type: "image/svg+xml",
						purpose: "maskable",
					},
					{
						src: "/assets/pos_next/pos/icon-maskable.svg",
						sizes: "512x512",
						type: "image/svg+xml",
						purpose: "maskable",
					},
				],
			},
			workbox: {
                                navigateFallback: null,
				globPatterns: ["**/*.{js,css,html,ico,png,svg,woff,woff2}"],
				maximumFileSizeToCacheInBytes: 4 * 1024 * 1024, // 3 MB
                                modifyURLPrefix: {
                                        "": "/assets/pos_next/pos/",
                                },
                                runtimeCaching: [
                                        {
                                                urlPattern: ({ request, url }) =>
                                                        request.mode === "navigate" &&
                                                        url.origin === self.location.origin &&
                                                        /^\/pos(?:\/|$)/.test(url.pathname),
                                                handler: "NetworkFirst",
                                                options: {
                                                        cacheName: "pos-navigation-cache",
                                                        networkTimeoutSeconds: 5,
                                                        precacheFallback: {
                                                                fallbackURL: "/assets/pos_next/pos/offline-shell.html",
                                                        },
                                                        plugins: [
                                                                {
                                                                        fetchDidSucceed: async function ({ response }) {
                                                                                if ([500, 502, 503, 504].includes(response.status)) {
                                                                                        throw new Error(
                                                                                                `ERPNext unavailable: HTTP ${response.status}`
                                                                                        );
                                                                                }
                                                                                return response;
                                                                        },
                                                                },
                                                        ],
                                                        cacheableResponse: {
                                                                statuses: [200],
                                                        },
                                                        expiration: {
                                                                maxEntries: 5,
                                                                maxAgeSeconds: 60 * 60 * 24 * 7,
                                                        },
                                                },
                                        },
                                        {
                                                urlPattern: /^https:\/\/fonts\.googleapis\.com\/.*/i,
						handler: "CacheFirst",
						options: {
							cacheName: "google-fonts-cache",
							expiration: {
								maxEntries: 10,
								maxAgeSeconds: 60 * 60 * 24 * 365, // 1 year
							},
							cacheableResponse: {
								statuses: [0, 200],
							},
						},
					},
					{
						urlPattern: /^https:\/\/fonts\.gstatic\.com\/.*/i,
						handler: "CacheFirst",
						options: {
							cacheName: "gstatic-fonts-cache",
							expiration: {
								maxEntries: 10,
								maxAgeSeconds: 60 * 60 * 24 * 365, // 1 year
							},
							cacheableResponse: {
								statuses: [0, 200],
							},
						},
					},
					{
						urlPattern: /\/assets\/pos_next\/pos\/.*/i,
						handler: "CacheFirst",
						options: {
							cacheName: "pos-assets-cache",
							expiration: {
								maxEntries: 500,
								maxAgeSeconds: 60 * 60 * 24 * 30, // 30 days
							},
						},
					},
					// Cache product images with StaleWhileRevalidate for better UX
					{
						urlPattern: /\/files\/.*\.(jpg|jpeg|png|gif|webp|svg)$/i,
						handler: "StaleWhileRevalidate",
						options: {
							cacheName: "product-images-cache",
							expiration: {
								maxEntries: 200, // Cache up to 200 product images
								maxAgeSeconds: 60 * 60 * 24 * 7, // 7 days
							},
							cacheableResponse: {
								statuses: [0, 200],
							},
						},
					},

				],
				cleanupOutdatedCaches: true,
				skipWaiting: true,
				clientsClaim: true,
			},
			devOptions: {
				enabled: true,
				type: "module",
			},
		}),
	],
	build: {
		chunkSizeWarningLimit: 1500,
		outDir: "../pos_next/public/pos",
		emptyOutDir: true,
		target: "es2015",
		sourcemap: enableSourceMap,
	},
	worker: {
		format: "es",
		rollupOptions: {
			output: {
				format: "es",
			},
		},
	},
	resolve: {
		alias: {
			"@": path.resolve(__dirname, "src"),
			"tailwind.config.js": path.resolve(__dirname, "tailwind.config.js"),
		},
	},
	define: {
		__BUILD_VERSION__: JSON.stringify(buildVersion),
	},
	optimizeDeps: {
		include: ["feather-icons", "showdown", "highlight.js/lib/core", "interactjs", "qz-tray"],
	},
	server: {
		allowedHosts: true,
		port: 8080,
		proxy: {
			"^/(app|api|assets|files|printview)": {
				target: "http://127.0.0.1:8000",
				ws: true,
				changeOrigin: true,
				secure: false,
				cookieDomainRewrite: "localhost",
				router: (req) => {
					const site_name = req.headers.host.split(":")[0];
					// Support both localhost and 127.0.0.1
					const isLocalhost = site_name === "localhost" || site_name === "127.0.0.1";
					const targetHost = isLocalhost ? "127.0.0.1" : site_name;
					return `http://${targetHost}:8000`;
				},
			},
		},
	},
});
