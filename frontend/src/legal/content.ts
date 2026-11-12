/** The Privacy Policy and Terms of Service, as data - edit the wording
 * here, the /privacy and /terms pages just render it.
 *
 * Everything in [square brackets] is a detail only the business owner can
 * fill in (legal entity, address, governing law, retention periods). While
 * any remain, LEGAL_DRAFT stays true and the pages show a draft notice. */

export const LEGAL_DRAFT = true;
export const LAST_UPDATED = "12 November 2026";

const COMPANY = "Eluwa Prime Global Services LTD (CAC registration no. 8996524)";
const CONTACT = "privacy@myshopp.cc";
const ADDRESS = "12 Adams Estate, Osogbo, Osun State, Nigeria";

/** a string is a paragraph; a string[] is a bulleted list */
export type LegalBlock = string | string[];

export interface LegalSection {
  id: string;
  heading: string;
  body: LegalBlock[];
}

export interface LegalDocument {
  title: string;
  intro: string;
  sections: LegalSection[];
}

export const PRIVACY_POLICY: LegalDocument = {
  title: "Privacy Policy",
  intro: `This policy explains what information MyShop (operated by ${COMPANY}, "we", "us") collects, why, who it is shared with, how long it is kept, and the choices you have. It covers the MyShop web app at app.myshopp.cc, its API at api.myshopp.cc, and the emails we send.`,
  sections: [
    {
      id: "roles",
      heading: "1. Who is responsible for what",
      body: [
        "MyShop is used by businesses (\"you\", our customer) to keep records about their own customers (\"your customers\"). That gives us two different roles:",
        [
          "For your account - your name, login email, password, and business profile - we decide how the information is used, so we are responsible for it (the \"controller\").",
          "For the records you keep about your customers - names, contact details, purchases, orders, notes and anything else you add - you decide what is collected and why. We store and process it only to provide MyShop to you, on your instructions (we are your \"processor\"). If one of your customers asks about their data, they should contact you; we will help you answer them.",
        ],
      ],
    },
    {
      id: "collect",
      heading: "2. Information we collect",
      body: [
        "Information you give us:",
        [
          "Account details: your name, email address, a securely hashed password (we never store it in readable form), or - if you sign in with Google - your Google account identifier and email.",
          "Business profile: business name, industry, team size, manager and staff names, phone, address, brand colour, default currency, support email and sending address.",
          "Customer records you add or import: names, phone numbers, email addresses, birthdays, addresses, occupation, interests, consent dates, transactions and line items, orders, notes, custom fields, and photos or documents you share with the assistant.",
          "Content you create: email templates, messages you send, segments (including custom SQL you write), forms, saved dashboard widgets, webhook settings, and your conversations with the assistant.",
        ],
        "Information collected when your customers interact with you through MyShop:",
        [
          "Submissions to public forms you share (for example a sign-up form), which are added to your customer records.",
          "Delivery results for emails you send them (sent, failed, skipped).",
        ],
        "Information collected automatically:",
        [
          "Technical logs needed to run and secure the service: IP address, browser type, request times and errors. Our hosting providers keep similar logs.",
          "Small pieces of data stored in your browser (local storage) to keep you signed in and remember preferences such as light/dark theme and button positions. We do not use advertising or cross-site tracking cookies.",
        ],
      ],
    },
    {
      id: "use",
      heading: "3. How we use information",
      body: [
        [
          "To provide MyShop: storing your records, showing dashboards, resolving segments, filling in merge tags, sending the emails you ask us to send, and running the assistant.",
          "To secure your account: verifying your email, password resets, preventing abuse, and investigating problems.",
          "To send you service messages: verification, password reset, notifications about actions in your account. We do not send you marketing without your agreement.",
          "To improve accuracy, as described in section 5.",
          "To meet legal obligations and enforce our Terms of Service.",
        ],
        "We do not sell personal information, and we do not use your customers' data to advertise to them or to anyone else.",
      ],
    },
    {
      id: "ai",
      heading: "4. The AI assistant and other AI features",
      body: [
        "Several features use AI language models: the chat assistant, reading photos and documents you share with it, turning a description into segment filters or SQL, \"Ask your data\", and writing emails. To answer a request, we send the relevant part of your data (for example the customers or purchases the request is about) to an AI provider and receive its answer back.",
        "Current AI providers: Groq, Google (Gemini) and OpenRouter (which routes requests to models run by other companies). Each provider processes requests under its own terms. Depending on the provider and plan, a provider may keep requests for a limited time for abuse monitoring, and some free plans permit the provider to use requests to improve its models. [Review each provider's current data-use terms and list the retention period here, or switch to plans with zero data retention.]",
        "AI output can be wrong. Actions that reach real people or cannot be undone - sending email, deleting or merging customers - always wait for a person to confirm them.",
      ],
    },
    {
      id: "improve",
      heading: "5. Using a sample of data to improve accuracy",
      body: [
        "To make the assistant more accurate (for example, better at reading receipts or understanding requests), we may review and use a sample of AI interactions and related records - no more than 70% of them.",
        [
          "Before use, the sample is de-identified: names, phone numbers, email addresses and other direct identifiers are removed or replaced with irreversible hashes.",
          "The sample is used only to evaluate and improve MyShop's own features. It is not sold, and is not used to train models offered to other companies.",
          "Access is limited to the people who need it for this purpose.",
          `You can opt out at any time by writing to ${CONTACT}; future interactions from your account will then be excluded.`,
        ],
      ],
    },
    {
      id: "share",
      heading: "6. Who we share information with",
      body: [
        "We share information only with service providers who help us run MyShop, under agreements that limit their use of it, and only as needed:",
        [
          "Supabase - database hosting.",
          "Render - hosting for our API and background work.",
          "Vercel - hosting for the web app.",
          "Resend - delivering emails (account emails and the emails you send your customers).",
          "Google - \"Continue with Google\" sign-in, if you use it.",
          "Groq, Google and OpenRouter - AI features (see section 4).",
          "Cloudflare - domain name services.",
        ],
        "We also share information:",
        [
          "Where you tell us to - for example, webhooks send record changes to the web addresses you configure, and exports download to your device.",
          "If required by law, or to protect the rights, property or safety of our users, the public or us.",
          "As part of a merger, acquisition or sale of assets, in which case this policy continues to apply to the information transferred.",
        ],
      ],
    },
    {
      id: "transfers",
      heading: "7. Where information is stored",
      body: [
        "Our providers operate in several countries, so information may be stored or processed outside the country where you or your customers live, including in [the United States / the European Union - confirm the Supabase region and providers' locations]. Where the law requires it, we rely on appropriate safeguards for these transfers.",
      ],
    },
    {
      id: "retention",
      heading: "8. How long we keep information",
      body: [
        [
          "Account and customer records are kept for as long as your account is open.",
          "Records you delete are removed from the live database straight away and from backups within 90 days.",
          "Technical logs are kept for up to 90 days unless needed to investigate a security issue.",
          "Email delivery records are kept for as long as your account is open, so you can see what was sent.",
        ],
      ],
    },
    {
      id: "termination",
      heading: "9. When you close your account",
      body: [
        "When your account is closed - by you, or when our agreement ends - we will:",
        [
          "Give you 90 days to export your data. During that time the account is read-only, and you can cancel the closure.",
          "Then permanently delete your account, your business profile and all your customer records, notes, transactions, orders, templates, messages, segments, forms and assistant conversations from our live systems, and from backups within a further 90 days.",
          "Irreversibly hash and anonymize any personal information from your account that was included in the accuracy sample described in section 5, so that it can no longer be linked to you or your customers.",
        ],
        "We may keep a minimal record that an account existed, and anything we are legally required to keep, for as long as the law requires.",
      ],
    },
    {
      id: "security",
      heading: "10. Security",
      body: [
        "We use encrypted connections (HTTPS) everywhere, store passwords only as salted hashes, keep each business's data separated from every other business's, and give staff access only where needed. Custom SQL segments run on a private, read-only copy of your own data, never directly on our database. No system is perfectly secure; if we learn of a breach affecting your information, we will tell you and, where required, the authorities, without undue delay.",
      ],
    },
    {
      id: "rights",
      heading: "11. Your choices and rights",
      body: [
        "Depending on where you live, you may have the right to access, correct, export or delete your personal information, to object to or restrict certain uses, to withdraw consent, and to complain to a data protection authority. Most of this you can do yourself in the app (editing records, exporting CSVs, deleting customers). For anything else, write to us at " + CONTACT + ". We may need to confirm your identity first.",
        "If you are one of our customers' customers, please contact the business that holds your information; we will support them in responding.",
      ],
    },
    {
      id: "children",
      heading: "12. Children",
      body: [
        "MyShop is a business tool and is not meant for anyone under 18. Businesses must not use it to collect information about children unless the law allows it and any required parental consent has been obtained.",
      ],
    },
    {
      id: "changes",
      heading: "13. Changes to this policy",
      body: [
        "We will post any changes here and update the date at the top. If a change is significant, we will tell you by email or in the app before it takes effect.",
      ],
    },
    {
      id: "contact",
      heading: "14. Contact",
      body: [`${COMPANY}, ${ADDRESS}. Email: ${CONTACT}.`],
    },
  ],
};

export const TERMS_OF_SERVICE: LegalDocument = {
  title: "Terms of Service",
  intro: `These terms are an agreement between you (the person or business using MyShop) and ${COMPANY} ("we", "us"). By creating an account or using MyShop you agree to them. If you are using MyShop for a business, you confirm you are allowed to accept these terms on its behalf.`,
  sections: [
    {
      id: "service",
      heading: "1. The service",
      body: [
        "MyShop helps small businesses keep customer records, track transactions and orders, build customer segments, send emails to their customers, and use an AI assistant to do this faster. We may add, change or remove features over time; if we remove something important you rely on, we will try to give you reasonable notice.",
      ],
    },
    {
      id: "account",
      heading: "2. Your account",
      body: [
        [
          "You must give accurate information when you sign up and keep it up to date.",
          "You are responsible for keeping your login details secure and for everything done through your account, including by people you share access with.",
          "Tell us straight away at ${CONTACT} if you think someone has accessed your account without permission.",
          "You must be at least 18 years old.",
        ],
      ],
    },
    {
      id: "your-data",
      heading: "3. Your data",
      body: [
        "You own the data you put into MyShop. You give us permission to store, process and display it only as needed to provide and improve the service as described in our Privacy Policy - including the de-identified accuracy sample described there.",
        "You are responsible for having the right to collect and use your customers' information, including any consent the law requires, and for telling your customers how you use their information. MyShop gives you tools (such as recording consent dates) but cannot decide this for you.",
      ],
    },
    {
      id: "messages",
      heading: "4. Emails you send through MyShop",
      body: [
        "Emails you send go out from your business's address on our sending domain, with replies going to you. When you send them:",
        [
          "Only email people who have agreed to hear from you, or where the law otherwise allows it. By default MyShop skips customers with no recorded consent; if you turn that off, you are responsible for the decision.",
          "Make it clear who the email is from, do not mislead about its content, and honour requests to stop - promptly stop emailing anyone who asks.",
          "Check emails before you send them, including any written by the assistant: merge tags fill in real customer data, and placeholders such as [discount] are sent exactly as written if you leave them in.",
        ],
        "We may pause sending from an account that causes high complaint or bounce rates, or that appears to be sending spam, to protect deliverability for everyone.",
      ],
    },
    {
      id: "ai",
      heading: "5. AI features",
      body: [
        "The assistant and other AI features can make mistakes - misreading a photo, picking the wrong customer, writing a wrong total or an awkward sentence. You are responsible for reviewing what they produce before relying on it or sending it to anyone. Actions that reach real people or cannot be undone wait for your confirmation; please read what you are confirming.",
      ],
    },
    {
      id: "acceptable-use",
      heading: "6. Acceptable use",
      body: [
        "You must not use MyShop to:",
        [
          "break any law, including data protection, consumer protection and anti-spam laws;",
          "send spam, phishing, malware, or misleading or harassing messages;",
          "store information you have no right to hold, or sensitive information (such as health or financial account details) without a lawful basis and appropriate care;",
          "try to access another business's data, probe or attack our systems, get around usage limits or security controls, or reverse-engineer the service except where the law allows;",
          "resell or provide the service to others without our written permission.",
        ],
      ],
    },
    {
      id: "fees",
      heading: "7. Fees",
      body: [
        "MyShop offers a free tier and paid tiers. The features and limits of each tier, and the price and billing terms of a paid tier, are set out in what we agree with you. You will not be charged unless you agree to a paid tier, and we will tell you before any change to the price of a tier you are on takes effect.",
      ],
    },
    {
      id: "third-parties",
      heading: "8. Third-party services",
      body: [
        "MyShop relies on other providers (listed in our Privacy Policy) for hosting, email delivery, sign-in and AI. Their services are subject to their own terms, and we are not responsible for their outages, though we will work to limit the effect on you.",
      ],
    },
    {
      id: "termination",
      heading: "9. Ending this agreement",
      body: [
        [
          "You can stop using MyShop and ask us to close your account at any time.",
          "We may suspend or close an account that breaks these terms, puts other users or the service at risk, or where the law requires it. Where reasonable, we will warn you first and give you a chance to fix the problem.",
          "When an account is closed, you will have 90 days to export your data (and can cancel the closure in that time). After that, all of your customer data is permanently deleted, and any personal information from your account used for improving accuracy is irreversibly hashed and anonymized, as set out in section 9 of our Privacy Policy.",
        ],
      ],
    },
    {
      id: "warranty",
      heading: "10. No warranty",
      body: [
        "We work hard to keep MyShop reliable and accurate, but it is provided \"as is\" and \"as available\". To the extent the law allows, we do not promise that it will be uninterrupted, error-free, or fit for a particular purpose. Keep your own exports of anything you cannot afford to lose.",
      ],
    },
    {
      id: "liability",
      heading: "11. Limits on liability",
      body: [
        "To the extent the law allows, we are not liable for indirect or consequential losses (such as lost profits, revenue or goodwill), and our total liability for any claim relating to MyShop is limited to the greater of the amount you paid us in the 12 months before the claim and ₦20,000. Nothing in these terms limits liability that cannot be limited by law, such as for fraud.",
      ],
    },
    {
      id: "indemnity",
      heading: "12. Your responsibility to us",
      body: [
        "If someone brings a claim against us because of data you put into MyShop, messages you sent through it, or your breach of these terms or the law, you agree to cover our reasonable costs of dealing with it, to the extent the law allows.",
      ],
    },
    {
      id: "changes",
      heading: "13. Changes to these terms",
      body: [
        "We may update these terms. We will post the new version here and update the date at the top; for significant changes we will notify you by email or in the app at least 15 days before they take effect. If you keep using MyShop after that, you accept the new terms.",
      ],
    },
    {
      id: "law",
      heading: "14. Governing law",
      body: [
        "These terms are governed by the laws of the Federal Republic of Nigeria, and disputes will be handled by the courts of Osun State, Nigeria, unless the law where you live gives you the right to bring a claim locally.",
      ],
    },
    {
      id: "contact",
      heading: "15. Contact",
      body: [`${COMPANY}, ${ADDRESS}. Email: ${CONTACT}.`],
    },
  ],
};
