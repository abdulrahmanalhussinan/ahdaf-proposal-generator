"""Platform knowledge used to tailor social/content proposals. Qualitative only — no audience numbers."""

PLATFORMS = {
    "tiktok": {
        "label": "تيك توك",
        "patterns": [r"تيك\s?توك", r"tik\s?tok"],
        "role": "منصة اكتشاف؛ يصل فيها الفيديو إلى غير المتابعين بحسب اهتماماتهم، وتكافئ المحتوى القصير السريع الذي يبدو طبيعيًا لا إعلانيًا",
        "formats": ["فيديوهات قصيرة بإيقاع سريع", "مواكبة الترندات المناسبة للعلامة", "بث مباشر عند المناسبات"],
        "kpis": ["video_views", "engagement_rate", "follower_growth", "completion_rate"],
    },
    "instagram": {
        "label": "إنستقرام",
        "patterns": [r"[اإ]نستقرام", r"[اإ]نستغرام", r"[اإ]نستا\b", r"instagram", r"\binsta\b"],
        "role": "الواجهة البصرية للعلامة؛ يزورها العميل ليتحقق من الجودة والمصداقية قبل أن يقرر، وتجمع بين الريلز والقصص والمنشورات الثابتة",
        "formats": ["ريلز", "قصص يومية", "منشورات وكاروسيل", "الهايلايت كمرجع دائم"],
        "kpis": ["reach", "engagement_rate", "profile_visits", "follower_growth"],
    },
    "snapchat": {
        "label": "سناب شات",
        "patterns": [r"سناب", r"snap\s?chat", r"\bsnap\b"],
        "role": "منصة الاستخدام اليومي في السعودية؛ تناسب المحتوى العفوي والعروض السريعة والاستهداف الجغرافي",
        "formats": ["قصص يومية عفوية", "محتوى من الموقع", "إعلانات بين القصص", "فلاتر وعدسات للمناسبات"],
        "kpis": ["story_views", "reach", "swipe_ups"],
    },
    "x": {
        "label": "إكس",
        "patterns": [r"تويتر", r"twitter", r"\bإكس\b", r"\bاكس\b", r"\(x\)", r"منصة x", r"x\.com"],
        "role": "منصة الحوار والأخبار؛ مناسبة للإعلانات الرسمية ومتابعة النقاشات العامة والرد السريع على الاستفسارات",
        "formats": ["تغريدات وسلاسل", "تغطيات حية", "مساحات صوتية", "ردود وخدمة عملاء"],
        "kpis": ["impressions", "engagement_rate", "mentions"],
    },
    "linkedin": {
        "label": "لينكدإن",
        "patterns": [r"لينكد", r"linked\s?in"],
        "role": "منصة القرار المهني؛ تخاطب المديرين وأصحاب القرار في الشركات، وتناسب محتوى الخبرة والإنجازات والتوظيف",
        "formats": ["مقالات ومنشورات خبرة", "إعلانات الإنجازات والشراكات", "محتوى الفريق وثقافة العمل"],
        "kpis": ["impressions", "engagement_rate", "follower_growth"],
    },
    "youtube": {
        "label": "يوتيوب",
        "patterns": [r"يوتيوب", r"youtube"],
        "role": "منصة المحتوى الطويل والبحث؛ تناسب الشروحات والأفلام التعريفية والإعلانات قبل الفيديو",
        "formats": ["فيديوهات تعريفية وشروحات", "شورتس", "إعلانات قبل الفيديو"],
        "kpis": ["video_views", "watch_time", "subscribers"],
    },
    "whatsapp": {
        "label": "واتساب أعمال",
        "patterns": [r"واتس", r"whats\s?app"],
        "role": "قناة التحويل المباشر؛ يكمل فيها العميل استفساره أو طلبه بعد أن يجذبه المحتوى",
        "formats": ["ردود جاهزة", "كتالوج المنتجات", "رسائل المتابعة"],
        "kpis": ["leads", "response_time"],
    },
    "google": {
        "label": "إعلانات قوقل",
        "patterns": [r"قوقل", r"جوجل", r"google"],
        "role": "تلتقط الطلب القائم لحظة البحث، وتناسب الخدمات التي يبحث عنها العميل بنفسه",
        "formats": ["إعلانات البحث", "الإعلانات المحلية على الخرائط", "شبكة العرض"],
        "kpis": ["ctr", "cpc", "conversions"],
    },
}

PLATFORM_ORDER = ["tiktok", "instagram", "snapchat", "x", "linkedin", "youtube", "whatsapp", "google"]
