/**
 * Small self-contained dictionary for the Intelligence workspace.
 *
 * Keys are the English strings, values the Persian translation. Anything that is
 * not translated falls back to English, so adding a string to a component can
 * never break the UI.
 */

const FA: Record<string, string> = {
	Intelligence: 'اطلاعات و تحلیل',
	'Intelligence workspace': 'فضای کار اطلاعاتی',
	'Local-first workspace': 'فضای کاری محلی',
	'Everything runs on your own machine — models, documents and flight data stay offline.':
		'همه‌چیز روی ماشین خودت اجرا می‌شود — مدل‌ها، اسناد و داده پروازها آفلاین می‌مانند.',
	'Choose a workspace': 'یک فضای کار انتخاب کن',
	'Pick the mode that matches your question. You can switch at any time.':
		'حالتی را انتخاب کن که با پرسش تو جور است. هر زمان می‌توانی تغییر بدهی.',

	'Topic Expert': 'متخصص موضوعی',
	'Flight Intelligence': 'اطلاعات پرواز',
	'File Analyst': 'تحلیل فایل',
	'Flight intelligence': 'اطلاعات پرواز',
	'File analyst': 'تحلیل فایل',
	Open: 'باز کن',
	Home: 'خانه',
	'All workspaces': 'همه فضاهای کار',
	'Data source': 'منبع داده',
	'Elasticsearch connected': 'اتصال به Elasticsearch',
	'Elasticsearch offline': 'Elasticsearch در دسترس نیست',
	'Demo dataset': 'داده نمایشی',
	'Demo data': 'داده نمایشی',
	Index: 'ایندکس',
	Documents: 'سند',
	'Time field': 'فیلد زمان',
	'Trajectory field': 'فیلد مسیر',
	Schema: 'ساختار داده',
	Reconnect: 'اتصال مجدد',
	Close: 'بستن',
	'Not configured': 'تنظیم نشده',
	'not detected': 'شناسایی نشد',
	Configuration: 'تنظیمات',
	'Set ELASTICSEARCH_URL (or INTEL_ELASTICSEARCH_URL) and INTEL_ELASTICSEARCH_INDEX to connect your data.':
		'برای اتصال داده، ELASTICSEARCH_URL (یا INTEL_ELASTICSEARCH_URL) و INTEL_ELASTICSEARCH_INDEX را تنظیم کن.',
	'Open the setup guide': 'راهنمای راه‌اندازی',

	Model: 'مدل',
	'No local model is available yet.': 'هنوز مدل محلی در دسترس نیست.',
	'Add a model connection (Ollama or an OpenAI-compatible server) in Open WebUI, then reload this page.':
		'در Open WebUI یک اتصال مدل (Ollama یا سرور سازگار با OpenAI) اضافه کن و سپس این صفحه را دوباره بارگذاری کن.',
	Send: 'ارسال',
	Stop: 'توقف',
	'Clear conversation': 'پاک کردن گفتگو',
	Retry: 'تلاش مجدد',
	Copy: 'کپی',
	Copied: 'کپی شد',
	Sources: 'منابع',
	'Grounded in {n} source(s)': 'مستند به {n} منبع',
	'Ask a question…': 'پرسش خود را بنویس…',
	'Ask about the selected aircraft…': 'درباره هواپیماهای انتخاب‌شده بپرس…',
	'Ask about your documents…': 'درباره اسنادت بپرس…',
	'Answering…': 'در حال پاسخ…',
	'Thinking…': 'در حال اندیشیدن…',
	You: 'شما',
	Assistant: 'دستیار',
	'Preparing context…': 'در حال آماده‌سازی زمینه…',

	'Time window': 'بازه زمانی',
	'Last hour': 'یک ساعت اخیر',
	'Last 6 hours': '۶ ساعت اخیر',
	'Last 24 hours': '۲۴ ساعت اخیر',
	'Last 7 days': '۷ روز اخیر',
	Custom: 'سفارشی',
	From: 'از',
	To: 'تا',
	Apply: 'اعمال',
	'Callsign, route, status…': 'کال‌ساین، مسیر، وضعیت…',
	Refresh: 'به‌روزرسانی',
	Aircraft: 'هواپیما',
	'Select all': 'انتخاب همه',
	Clear: 'پاک کردن',
	'No aircraft in this time window.': 'در این بازه زمانی هواپیمایی نیست.',
	'Could not load flights': 'بارگیری پروازها ناموفق بود',
	'Loading…': 'در حال بارگیری…',
	Callsign: 'کال‌ساین',
	Route: 'مسیر',
	Altitude: 'ارتفاع',
	Speed: 'سرعت',
	'Last seen': 'آخرین مشاهده',
	Points: 'نقاط',
	'No position': 'بدون موقعیت',
	'Select one or more aircraft to draw their positions and trajectories.':
		'یک یا چند هواپیما انتخاب کن تا موقعیت و مسیرشان روی نقشه رسم شود.',
	'Selected aircraft': 'هواپیماهای انتخاب‌شده',
	'Fit map to selection': 'تنظیم نقشه روی انتخاب',
	'Clear selection': 'پاک کردن انتخاب',
	'Trajectory points': 'نقاط مسیر',
	'Position unavailable': 'موقعیت در دسترس نیست',
	'Live map': 'نقشه زنده',
	'Offline vector basemap': 'نقشه برداری آفلاین',
	'Online map tiles': 'کاشی‌های نقشه آنلاین',
	Elasticsearch: 'الاستیک‌سرچ',
	'Latest state per aircraft': 'آخرین وضعیت هر هواپیما',
	'Extend the time window to see more aircraft.':
		'بازه زمانی را گسترده‌تر کن تا هواپیماهای بیشتری ببینی.',
	'Filtered from': 'فیلترشده از',
	of: 'از',
	'{n} aircraft': '{n} هواپیما',
	'{n} documents': '{n} سند',
	'Showing latest state': 'نمایش آخرین وضعیت',

	'Upload documents': 'بارگذاری اسناد',
	'Drop files here or click to browse': 'فایل‌ها را اینجا رها کن یا برای انتخاب کلیک کن',
	'PDF, text, markdown, CSV, JSON, DOCX, XLSX. Files are parsed locally.':
		'PDF، متن، مارک‌داون، CSV، JSON، DOCX، XLSX. فایل‌ها به‌صورت محلی پردازش می‌شوند.',
	'Uploading…': 'در حال بارگذاری…',
	'Processing…': 'در حال پردازش…',
	Ready: 'آماده',
	Remove: 'حذف',
	'No text could be extracted from this file.': 'متنی از این فایل استخراج نشد.',
	'File uploads are disabled for your account.': 'بارگذاری فایل برای حساب تو غیرفعال است.',
	'Ask questions about one or more files. The most relevant passages are retrieved locally and sent to your model.':
		'درباره یک یا چند فایل پرسش کن. مرتبط‌ترین بخش‌ها به‌صورت محلی بازیابی و به مدل تو فرستاده می‌شوند.',
	'No documents yet': 'هنوز سندی اضافه نشده',
	'Add a file to start asking questions about its content.':
		'یک فایل اضافه کن تا پرسش درباره محتوای آن آغاز شود.',
	Document: 'سند',
	Chunk: 'بخش',
	'Clear all': 'پاک کردن همه',
	'{n} file(s)': '{n} فایل',
	characters: 'کاراکتر',
	Disabled: 'غیرفعال',
	'This workspace is disabled on this server. Ask an administrator to set INTEL_ENABLE=true to switch it on.':
		'این فضای کار روی این سرور غیرفعال است. از مدیر بخواه INTEL_ENABLE=true را تنظیم کند.',
	'Processing failed': 'پردازش فایل ناموفق بود',

	'Answer in English': 'پاسخ به انگلیسی',
	'Answer in Persian': 'پاسخ به فارسی',
	'Answer language': 'زبان پاسخ',

	'Read the setup guide': 'راهنمای راه‌اندازی را بخوان',
	'Elasticsearch is not configured, so the workspace is showing a synthetic demo dataset. Set ELASTICSEARCH_URL to use your own index.':
		'Elasticsearch تنظیم نشده است، بنابراین فضای کار یک مجموعه داده نمایشی نشان می‌دهد. برای استفاده از ایندکس خودت، ELASTICSEARCH_URL را تنظیم کن.',
	'Could not reach Elasticsearch.': 'اتصال به Elasticsearch برقرار نشد.',
	'Retry connection': 'تلاش مجدد برای اتصال',
	Dismiss: 'بستن'
};

export type Translate = (key: string, vars?: Record<string, string | number>) => string;

export const createIntelTranslator = (locale?: string): Translate => {
	const fa = (locale ?? '').toLowerCase().startsWith('fa');
	return (key: string, vars?: Record<string, string | number>) => {
		let value = (fa && FA[key]) || key;
		if (vars) {
			for (const [name, replacement] of Object.entries(vars)) {
				value = value.replaceAll(`{${name}}`, String(replacement));
			}
		}
		return value;
	};
};

export const formatNumber = (value: number | null | undefined, locale?: string): string => {
	if (value === null || value === undefined || Number.isNaN(value)) return '—';
	const fa = (locale ?? '').toLowerCase().startsWith('fa');
	try {
		return new Intl.NumberFormat(fa ? 'fa-IR' : 'en-US').format(value);
	} catch {
		return String(value);
	}
};

export const formatDateTime = (value?: string | null, locale?: string): string => {
	if (!value) return '—';
	const date = new Date(value);
	if (Number.isNaN(date.getTime())) return '—';
	const fa = (locale ?? '').toLowerCase().startsWith('fa');
	try {
		return new Intl.DateTimeFormat(fa ? 'fa-IR' : 'en-GB', {
			month: 'short',
			day: '2-digit',
			hour: '2-digit',
			minute: '2-digit',
			hour12: false
		}).format(date);
	} catch {
		return date.toISOString();
	}
};
