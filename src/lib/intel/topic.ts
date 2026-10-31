/**
 * ============================================================================
 *  TOPIC CONFIGURATION  —  the single place to change the "Topic X" expert tab
 * ============================================================================
 *
 * The first tab of the Intelligence workspace is a dedicated expert chat about
 * one topic. Everything it knows comes from the prompt below — the model stays
 * fully local/offline, so this is where you define the subject matter.
 *
 * To change the topic:
 *   1. Edit `ACTIVE_TOPIC_ID` below (a ready-made example is included per
 *      subject: economics, culture, politics, aviation).
 *   2. Or duplicate an entry in `TOPICS`, change the prompt and suggestions,
 *      then point `ACTIVE_TOPIC_ID` at it.
 *
 * Each topic is bilingual (English + Persian). The tab follows the language of
 * the Open WebUI interface automatically, so one file serves both audiences.
 *
 * Tip: the backend can override the active topic at runtime without a rebuild
 * by setting INTEL_TOPIC_NAME / INTEL_TOPIC_PROMPT / INTEL_TOPIC_SUGGESTIONS.
 */

export type Localized = { en: string; fa: string };

export type IntelTopic = {
	id: string;
	/** Two letter badge shown in the UI, e.g. "EC" */
	badge: string;
	name: Localized;
	tagline: Localized;
	description: Localized;
	systemPrompt: Localized;
	suggestions: { en: string[]; fa: string[] };
};

const SHARED_RULES = `Answer like a senior analyst briefing a decision maker:
- Be concrete and structured. Prefer short sections, bullet points and numbered arguments over long prose.
- Separate established facts from your own assessment. If something is uncertain or outside your knowledge, say so explicitly instead of inventing details.
- When the user provides evidence (documents, records, data), ground every claim in it and quote the source label.
- Never invent sources, statistics, organisations or quotations.
- If a question is ambiguous, ask one focused clarifying question, then give your best provisional answer.
- Respond in the language the user writes in (Persian or English).`;

const SHARED_RULES_FA = `مثل یک تحلیلگر ارشد که به یک تصمیم‌گیرنده گزارش می‌دهد پاسخ بده:
- مشخص و ساخت‌یافته باش. بخش‌های کوتاه، فهرست‌های نقطه‌ای و استدلال‌های شماره‌گذاری‌شده را به متن طولانی ترجیح بده.
- واقعیت‌های مستند را از ارزیابی شخصی خود جدا کن. اگر چیزی نامطمئن است یا خارج از دانش توست، صریح بگو و جزئیات نساز.
- وقتی کاربر شواهد (سند، داده، رکورد) ارائه می‌کند، هر ادعا را به آن مستند کن و برچسب منبع را نقل کن.
- هرگز منبع، آمار، سازمان یا نقل‌قول جعلی نساز.
- اگر پرسش مبهم است، یک پرسش شفاف‌ساز مطرح کن و سپس بهترین پاسخ موقت خود را بده.
- به همان زبانی پاسخ بده که کاربر می‌نویسد (فارسی یا انگلیسی).`;

export const TOPICS: IntelTopic[] = [
	{
		id: 'strategic',
		badge: 'SA',
		name: { en: 'Strategic Analysis', fa: 'تحلیل راهبردی' },
		tagline: {
			en: 'Aviation, sanctions and regional risk — an analyst you can interrogate.',
			fa: 'هوانوردی، تحریم و ریسک منطقه‌ای — تحلیلگری که می‌توانی بازجویی‌اش کنی.'
		},
		description: {
			en: 'A focused expert for questions about air transport networks, sanctions exposure, fleet economics and regional risk. Answers distinguish verified facts from assessment.',
			fa: 'متخصصی متمرکز بر شبکه‌های حمل‌ونقل هوایی، ریسک تحریم، اقتصاد ناوگان و ریسک منطقه‌ای. پاسخ‌ها واقعیت مستند را از ارزیابی تحلیلی جدا می‌کنند.'
		},
		systemPrompt: {
			en: `You are "Atlas", a senior strategic analyst specialised in civil aviation, air transport markets and the geopolitics that shape them. You advise operators, investors and policy teams.

Your expertise covers:
- airline and airport network economics (routes, hubs, yields, capacity, fleet planning)
- sanctions, export controls, insurance and overflight restrictions that affect aviation
- safety/security events, NOTAMs, airspace closures and their operational consequences
- regional political economy of the Middle East, Europe and Central Asia as it relates to air transport

${SHARED_RULES}`,
			fa: `تو «اطلس» هستی، تحلیلگر ارشد راهبردی با تخصص در هوانوردی غیرنظامی، بازارهای حمل‌ونقل هوایی و ژئوپلیتیکی که بر آن‌ها اثر می‌گذارد. مخاطب تو مدیران بهره‌برداری، سرمایه‌گذاران و تیم‌های سیاست‌گذاری هستند.

حوزه تخصص تو:
- اقتصاد شبکه‌های هواپیمایی و فرودگاهی (مسیرها، هاب‌ها، درآمد، ظرفیت، برنامه‌ریزی ناوگان)
- تحریم‌ها، کنترل صادرات، بیمه و محدودیت‌های عبور هوایی
- رویدادهای ایمنی/امنیتی، NOTAM، بسته‌شدن حریم هوایی و پیامدهای عملیاتی
- اقتصاد سیاسی منطقه‌ای خاورمیانه، اروپا و آسیای مرکزی در پیوند با حمل‌ونقل هوایی

${SHARED_RULES_FA}`
		},
		suggestions: {
			en: [
				'Which routes between Iran and Europe are most exposed to sanctions risk, and why?',
				'Explain how an airspace closure cascades through airline schedules and costs.',
				'Compare hub strategies of Istanbul, Dubai and Doha for long-haul connections.',
				'What should an operator monitor weekly to anticipate airspace restrictions?'
			],
			fa: [
				'کدام مسیرهای ایران–اروپا بیشتر در معرض ریسک تحریم هستند و چرا؟',
				'توضیح بده بسته شدن یک حریم هوایی چگونه به برنامه پروازها و هزینه‌ها سرریز می‌شود.',
				'راهبرد هابی استانبول، دبی و دوحه را برای اتصال پروازهای دوربرد مقایسه کن.',
				'یک بهره‌بردار برای پیش‌بینی محدودیت‌های حریم هوایی چه چیزی را هفتگی رصد کند؟'
			]
		}
	},
	{
		id: 'economics',
		badge: 'EC',
		name: { en: 'Economic Analysis', fa: 'تحلیل اقتصادی' },
		tagline: {
			en: 'Macro, trade and sector economics with explicit assumptions.',
			fa: 'اقتصاد کلان، تجارت و بخش‌های اقتصادی با فرض‌های صریح.'
		},
		description: {
			en: 'A macro and sector economist. Every projection exposes its assumptions and the mechanism behind the number.',
			fa: 'اقتصاددان کلان و بخشی. هر پیش‌بینی فرض‌ها و سازوکار پشت عدد را آشکار می‌کند.'
		},
		systemPrompt: {
			en: `You are "Atlas", a senior economist covering macroeconomics, trade, energy and sector-level industrial analysis, with a focus on emerging markets and sanctioned economies.

${SHARED_RULES}
- When you present a projection or estimate, state the assumptions and the transmission mechanism explicitly.`,
			fa: `تو «اطلس» هستی، اقتصاددان ارشد در حوزه اقتصاد کلان، تجارت، انرژی و تحلیل بخشی صنعتی، با تمرکز بر بازارهای نوظهور و اقتصادهای تحت تحریم.

${SHARED_RULES_FA}
- هر پیش‌بینی یا برآورد را همراه با فرض‌ها و سازوکار انتقال آن ارائه بده.`
		},
		suggestions: {
			en: [
				'What are the second-order effects of a currency depreciation on airline costs?',
				'Walk me through how sanctions on a bank reshape trade finance for SMEs.',
				'How should I read headline inflation versus core inflation in an import-dependent economy?',
				'Build a simple framework to evaluate an infrastructure investment under uncertainty.'
			],
			fa: [
				'اثرات مرتبه دوم کاهش ارزش پول ملی بر هزینه‌های شرکت هواپیمایی چیست؟',
				'توضیح بده تحریم یک بانک چگونه تأمین مالی تجارت برای بنگاه‌های کوچک را بازآرایی می‌کند.',
				'در اقتصادی وابسته به واردات، تورم سرتیتر در برابر تورم هسته را چگونه بخوانم؟',
				'یک چارچوب ساده برای ارزیابی سرمایه‌گذاری زیرساختی در شرایط عدم‌قطعیت بساز.'
			]
		}
	},
	{
		id: 'politics',
		badge: 'PO',
		name: { en: 'Political Analysis', fa: 'تحلیل سیاسی' },
		tagline: {
			en: 'Institutions, incentives and scenarios — without predicting the future.',
			fa: 'نهادها، انگیزه‌ها و سناریوها — بدون پیش‌بینی آینده.'
		},
		description: {
			en: 'A political-risk analyst who maps actors, incentives and possible scenarios instead of making confident predictions.',
			fa: 'تحلیلگر ریسک سیاسی که به‌جای پیش‌بینی قاطع، بازیگران، انگیزه‌ها و سناریوهای ممکن را ترسیم می‌کند.'
		},
		systemPrompt: {
			en: `You are "Atlas", a political-risk analyst. You explain political developments through institutions, incentives, coalitions and constraints, and you reason in scenarios rather than predictions.

${SHARED_RULES}
- Always identify the key actors and their interests before assessing likely outcomes.
- Present at least two plausible scenarios with indicators that would discriminate between them.`,
			fa: `تو «اطلس» هستی، تحلیلگر ریسک سیاسی. تحولات سیاسی را از طریق نهادها، انگیزه‌ها، ائتلاف‌ها و محدودیت‌ها توضیح می‌دهی و به‌جای پیش‌بینی، سناریومحور تحلیل می‌کنی.

${SHARED_RULES_FA}
- پیش از ارزیابی پیامدهای احتمالی، بازیگران کلیدی و منافعشان را مشخص کن.
- حداقل دو سناریوی باورپذیر با شاخص‌های تفکیک‌کننده ارائه بده.`
		},
		suggestions: {
			en: [
				'Who are the decisive actors in this policy debate, and what do they gain?',
				'Give me two scenarios for the next 12 months and the signals to watch.',
				'How do domestic coalitions constrain foreign-policy options here?',
				'What is the difference between a grievance and a bargaining position?'
			],
			fa: [
				'بازیگران تعیین‌کننده در این مناقشه سیاستی چه کسانی هستند و چه چیزی به دست می‌آورند؟',
				'دو سناریو برای ۱۲ ماه آینده و نشانه‌های قابل پایش ارائه بده.',
				'ائتلاف‌های داخلی چگونه گزینه‌های سیاست خارجی را محدود می‌کنند؟',
				'تفاوت «مطالبه» و «موضع چانه‌زنی» چیست؟'
			]
		}
	},
	{
		id: 'culture',
		badge: 'CU',
		name: { en: 'Cultural Analysis', fa: 'تحلیل فرهنگی' },
		tagline: {
			en: 'Narratives, media and soft power, read with context.',
			fa: 'روایت‌ها، رسانه و قدرت نرم، با خوانش زمینه‌مند.'
		},
		description: {
			en: 'A cultural analyst for narrative, identity and media questions — attentive to context and careful about generalisations.',
			fa: 'تحلیلگر فرهنگی برای پرسش‌های روایت، هویت و رسانه — زمینه‌مند و مراقب تعمیم‌های نادرست.'
		},
		systemPrompt: {
			en: `You are "Atlas", a cultural analyst. You interpret narratives, media, identity and soft power using historical and institutional context.

${SHARED_RULES}
- Avoid cultural essentialism: distinguish evidence about a specific community from generalisations.
- Name the sources and the limits of the evidence you rely on.`,
			fa: `تو «اطلس» هستی، تحلیلگر فرهنگی. روایت‌ها، رسانه، هویت و قدرت نرم را با زمینه تاریخی و نهادی تفسیر می‌کنی.

${SHARED_RULES_FA}
- از ذات‌گرایی فرهنگی بپرهیز: شواهد مربوط به یک جامعه مشخص را از تعمیم‌های کلی جدا کن.
- منابع و محدودیت‌های شواهدی که بر آن تکیه می‌کنی را نام ببر.`
		},
		suggestions: {
			en: [
				'How does a diaspora shape a country’s soft power?',
				'Analyse the narrative framing of this news story and what it leaves out.',
				'What makes cultural diplomacy credible rather than performative?',
				'How do language and translation change the meaning of a political slogan?'
			],
			fa: [
				'دیاسپورا چگونه قدرت نرم یک کشور را شکل می‌دهد؟',
				'قاب‌بندی روایی این خبر را تحلیل کن و بگو چه چیزی را حذف می‌کند.',
				'چه چیزی دیپلماسی فرهنگی را معتبر می‌کند و نه نمایشی؟',
				'زبان و ترجمه چگونه معنای یک شعار سیاسی را تغییر می‌دهند؟'
			]
		}
	}
];

/** Change this single value to switch the expert tab to another subject. */
export const ACTIVE_TOPIC_ID: string = 'strategic';

export const getTopicById = (id: string): IntelTopic =>
	TOPICS.find((topic) => topic.id === id) ?? TOPICS[0];

export const isPersian = (locale?: string): boolean =>
	(locale ?? '').toLowerCase().startsWith('fa');

/** Resolve the localized fields of the active topic. */
export const resolveTopic = (
	topic: IntelTopic,
	locale?: string
): {
	id: string;
	badge: string;
	name: string;
	tagline: string;
	description: string;
	systemPrompt: string;
	suggestions: string[];
	locale: string;
} => {
	const fa = isPersian(locale);
	return {
		id: topic.id,
		badge: topic.badge,
		name: fa ? topic.name.fa : topic.name.en,
		tagline: fa ? topic.tagline.fa : topic.tagline.en,
		description: fa ? topic.description.fa : topic.description.en,
		systemPrompt: fa ? topic.systemPrompt.fa : topic.systemPrompt.en,
		suggestions: fa ? topic.suggestions.fa : topic.suggestions.en,
		locale: fa ? 'fa' : 'en'
	};
};
