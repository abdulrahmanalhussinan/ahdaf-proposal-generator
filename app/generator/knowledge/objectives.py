"""Objective categories. Each user-written objective is classified into one of
these, then rewritten as a measurable statement tied to KPIs. Targets come only
from numbers the user typed — otherwise the target is agreed with the client."""

OBJECTIVES = {
    "awareness": {
        "label": "رفع الوعي بالعلامة",
        "keywords": ["وعي", "الوعي", "انتشار", "الانتشار", "تعريف", "التعريف", "ظهور", "شهرة", "حضور العلامة", "معرفة"],
        "statement": "رفع مستوى معرفة {audience} {bi_client} خلال مدة المشروع، بقياس الوصول ومرات الظهور مقارنةً بخط الأساس عند البدء",
        "measures": ["reach", "impressions"],
    },
    "engagement": {
        "label": "تعزيز التفاعل",
        "keywords": ["تفاعل", "التفاعل", "مشاركة", "المشاركات", "تعليقات", "إعجاب"],
        "statement": "تحويل المشاهدة إلى تفاعل فعلي من {audience}، برفع معدل التفاعل على محتوى {client} وزيادة التعليقات والمشاركات والحفظ",
        "measures": ["engagement", "engagement_rate"],
    },
    "followers": {
        "label": "نمو قاعدة المتابعين",
        "keywords": ["متابع", "المتابعين", "متابعين", "قاعدة جماهيرية", "المشتركين", "مشترك"],
        "statement": "تنمية متابعي حسابات {client} من الشريحة المستهدفة تحديدًا، مع مراقبة جودة المتابعين لا عددهم فقط",
        "measures": ["follower_growth"],
    },
    "sales": {
        "label": "دعم المبيعات",
        "keywords": ["مبيعات", "المبيعات", "إيراد", "الإيرادات", "بيع", "شراء", "الطلبات", "طلبات", "تحويل", "التحويلات"],
        "statement": "ربط المحتوى والحملات بمسار شراء واضح يمكن تتبعه، بحيث تُنسب الطلبات إلى مصدرها وتُقاس تكلفة كل عملية بيع",
        "measures": ["conversions", "cpa"],
    },
    "bookings": {
        "label": "زيادة الحجوزات",
        "keywords": ["حجز", "حجوزات", "الحجوزات", "الحجز", "تأجير", "مواعيد"],
        "statement": "زيادة الحجوزات القادمة من القنوات الرقمية، مع تتبع مصدر كل حجز لمعرفة المنصة والمحتوى الأكثر تحويلًا",
        "measures": ["conversions", "cpa"],
    },
    "leads": {
        "label": "توليد العملاء المحتملين",
        "keywords": ["عملاء محتملين", "استفسار", "استفسارات", "leads", "تسجيل الاهتمام", "عملاء جدد", "طلبات تواصل"],
        "statement": "توليد طلبات واستفسارات مؤهلة من {audience}، مع قياس تكلفة الطلب ونسبة الطلبات الجادة منها",
        "measures": ["leads", "cpl"],
    },
    "traffic": {
        "label": "زيادة الزيارات",
        "keywords": ["زيارات", "الزيارات", "الموقع", "المتجر الإلكتروني", "زوار الموقع", "حركة"],
        "statement": "رفع عدد الزيارات النوعية إلى المنصات المملوكة لـ{client} من القنوات الرقمية، وتحسين نسبة من يكمل الرحلة بعد الزيارة",
        "measures": ["clicks", "ctr"],
    },
    "downloads": {
        "label": "زيادة تحميل التطبيق",
        "keywords": ["تحميل", "تنزيل", "التطبيق", "تطبيق"],
        "statement": "زيادة تحميل التطبيق وتسجيل المستخدمين الجدد، مع قياس تكلفة كل تحميل ونسبة المستخدمين النشطين بعده",
        "measures": ["installs", "cpi"],
    },
    "attendance": {
        "label": "تحقيق الحضور المستهدف",
        "keywords": ["حضور", "الحضور", "زوار", "الزوار", "المدعوين", "تسجيل", "التسجيل", "ضيوف"],
        "statement": "تحقيق حضور نوعي من {audience} يتوافق مع طبيعة الفعالية، عبر مسار دعوة وتسجيل وتأكيد واضح",
        "measures": ["attendance", "registration_rate"],
    },
    "coverage": {
        "label": "تحقيق تغطية إعلامية",
        "keywords": ["تغطية", "التغطية", "إعلامي", "الإعلام", "صحف", "صحفي", "وسائل الإعلام", "قنوات"],
        "statement": "تحقيق تغطية إعلامية في وسائل إعلام ذات صلة بالقطاع وبجمهور {client}، مع التركيز على جودة المنبر لا عدد الأخبار فقط",
        "measures": ["media_coverage", "pr_reach"],
    },
    "reputation": {
        "label": "تعزيز الصورة الذهنية",
        "keywords": ["سمعة", "السمعة", "الصورة الذهنية", "الثقة", "انطباع", "مصداقية"],
        "statement": "تعزيز الصورة الذهنية لـ{client} ورفع نسبة الحديث الإيجابي عنها، مع رصد مبكر لأي حديث سلبي ومعالجته",
        "measures": ["sentiment", "mentions"],
    },
    "launch": {
        "label": "إطلاق ناجح",
        "keywords": ["إطلاق", "اطلاق", "تدشين", "افتتاح", "الافتتاح", "منتج جديد", "خدمة جديدة"],
        "statement": "إطلاق {project} بحضور واضح في الأسابيع الأولى، وتعريف {audience} بما يقدمه وأين وكيف يصلون إليه",
        "measures": ["reach", "engagement"],
    },
    "content": {
        "label": "بناء مكتبة محتوى",
        "keywords": ["محتوى", "المحتوى", "إنتاج", "فيديوهات", "صور", "مكتبة"],
        "statement": "بناء مكتبة محتوى منتظمة بجودة ثابتة تخدم {client} خلال المشروع وبعده، وفق خطة نشر معتمدة",
        "measures": ["content_output", "on_time_delivery"],
    },
    "community": {
        "label": "بناء مجتمع حول العلامة",
        "keywords": ["مجتمع", "المجتمع", "ولاء", "الولاء", "علاقة", "ارتباط"],
        "statement": "بناء علاقة مستمرة مع {audience} تقوم على الرد السريع والمحتوى الذي يشاركهم لا يخاطبهم فقط",
        "measures": ["response_time", "engagement_rate"],
    },
    "positioning": {
        "label": "ترسيخ التموضع",
        "keywords": ["تموضع", "تمييز", "التميز", "هوية", "الهوية", "مكانة", "ريادة"],
        "statement": "ترسيخ تموضع واضح لـ{client} يميزها عن المنافسين، وتوحيد رسائلها عبر جميع نقاط التواصل",
        "measures": ["brand_consistency", "sentiment"],
    },
    "experience": {
        "label": "تجربة ضيوف متميزة",
        "keywords": ["تجربة", "رضا", "انطباع الضيوف", "ضيافة"],
        "statement": "تقديم تجربة متكاملة للضيوف من الدعوة حتى المغادرة، وقياس رضاهم باستبيان قصير بعد الفعالية",
        "measures": ["guest_satisfaction"],
    },
    "employer": {
        "label": "جاذبية بيئة العمل",
        "keywords": ["توظيف", "استقطاب", "المواهب", "بيئة العمل", "الموظفين"],
        "statement": "إبراز {client} كجهة عمل جاذبة للكفاءات عبر محتوى يعرض الفريق والثقافة والفرص بصدق",
        "measures": ["engagement_rate", "applications"],
    },
}

# Default objectives proposed when the user leaves the field empty (clearly marked as suggestions).
DEFAULTS_BY_TYPE = {
    "social_media": ["awareness", "engagement", "followers", "community"],
    "event": ["attendance", "experience", "coverage"],
    "pr": ["coverage", "reputation", "positioning"],
    "influencer": ["awareness", "engagement", "sales"],
    "campaign": ["awareness", "engagement", "sales"],
    "production": ["content", "positioning"],
    "branding": ["positioning", "awareness"],
    "exhibition": ["attendance", "leads", "positioning"],
    "digital_ads": ["sales", "leads", "traffic"],
    "content": ["content", "engagement", "positioning"],
    "other": ["awareness", "engagement"],
}
