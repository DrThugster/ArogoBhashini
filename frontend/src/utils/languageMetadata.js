// src/utils/languageMetadata.js

export const SUPPORTED_LANGUAGES = {
  en: {
    code: 'en',
    name: 'English',
    native: 'English',
    direction: 'ltr',
    supported: {
      tts: true,
      stt: true,
      translation: true
    },
    region: 'IN'
  },
  hi: {
    code: 'hi',
    name: 'Hindi',
    native: 'हिन्दी',
    direction: 'ltr',
    supported: {
      tts: true,
      stt: true,
      translation: true
    },
    region: 'IN'
  },
  as: {
    code: 'as',
    name: 'Assamese',
    native: 'অসমীয়া',
    direction: 'ltr',
    supported: {
      tts: true,
      stt: true,
      translation: true
    },
    region: 'IN'
  },
  bn: {
    code: 'bn',
    name: 'Bengali',
    native: 'বাংলা',
    direction: 'ltr',
    supported: {
      tts: true,
      stt: true,
      translation: true
    },
    region: 'IN'
  },
  bo: {
    code: 'bo',
    name: 'Bodo',
    native: 'बड़ो',
    direction: 'ltr',
    supported: {
      tts: true,
      stt: true,
      translation: true
    },
    region: 'IN'
  },
  gu: {
    code: 'gu',
    name: 'Gujarati',
    native: 'ગુજરાતી',
    direction: 'ltr',
    supported: {
      tts: true,
      stt: true,
      translation: true
    },
    region: 'IN'
  },
  kn: {
    code: 'kn',
    name: 'Kannada',
    native: 'ಕನ್ನಡ',
    direction: 'ltr',
    supported: {
      tts: true,
      stt: true,
      translation: true
    },
    region: 'IN'
  },
  ml: {
    code: 'ml',
    name: 'Malayalam',
    native: 'മലയാളം',
    direction: 'ltr',
    supported: {
      tts: true,
      stt: true,
      translation: true
    },
    region: 'IN'
  },
  mni: {
    code: 'mni',
    name: 'Manipuri',
    native: 'মণিপুরী',
    direction: 'ltr',
    supported: {
      tts: true,
      stt: true,
      translation: true
    },
    region: 'IN'
  },
  mr: {
    code: 'mr',
    name: 'Marathi',
    native: 'मराठी',
    direction: 'ltr',
    supported: {
      tts: true,
      stt: true,
      translation: true
    },
    region: 'IN'
  },
  or: {
    code: 'or',
    name: 'Oriya',
    native: 'ଓଡ଼ିଆ',
    direction: 'ltr',
    supported: {
      tts: true,
      stt: true,
      translation: true
    },
    region: 'IN'
  },
  pa: {
    code: 'pa',
    name: 'Punjabi',
    native: 'ਪੰਜਾਬੀ',
    direction: 'ltr',
    supported: {
      tts: true,
      stt: true,
      translation: true
    },
    region: 'IN'
  },
  raj: {
    code: 'raj',
    name: 'Rajasthani',
    native: 'राजस्थानी',
    direction: 'ltr',
    supported: {
      tts: true,
      stt: true,
      translation: true
    },
    region: 'IN'
  },
  ta: {
    code: 'ta',
    name: 'Tamil',
    native: 'தமிழ்',
    direction: 'ltr',
    supported: {
      tts: true,
      stt: true,
      translation: true
    },
    region: 'IN'
  },
  te: {
    code: 'te',
    name: 'Telugu',
    native: 'తెలుగు',
    direction: 'ltr',
    supported: {
      tts: true,
      stt: true,
      translation: true
    },
    region: 'IN'
  },
  ur: {
    code: 'ur',
    name: 'Urdu',
    native: 'اردو',
    direction: 'rtl',
    supported: {
      tts: true,
      stt: true,
      translation: true
    },
    region: 'IN'
  }
};

// Default language
export const DEFAULT_LANGUAGE = 'en';

// Voice options metadata
export const VOICE_OPTIONS = {
  genders: ['male', 'female', 'other'],
  labels: {
    male: 'Male',
    female: 'Female',
  },
  translations: {
    en: {
      male: 'Male',
      female: 'Female',
    },
    hi: {
          male: 'पुरुष',
          female: 'महिला',
        },
    as: {
          male: 'পুৰুষ',
          female: 'মহিলা',
        },
    bn: {
          male: 'পুরুষ',
          female: 'মহিলা',
        },
    bo: {
          male: 'पुरुष',
          female: 'महिला',
        },
    gu: {
          male: 'પુરુષ',
          female: 'મહિલા',
        },
    kn: {
          male: 'ಪುರುಷ',
          female: 'ಮಹಿಳೆ',
        },
    ml: {
          male: 'പുരുഷന്‍',
          female: 'സ്ത്രീ',
        },
    mni: {
          male: 'পুৰুষ',
          female: 'মহিলা',
        },
    mr: {
          male: 'पुरुष',
          female: 'महिला',
        },
    or: {
          male: 'ପୁରୁଷ',
          female: 'ମହିଳା',
        },
    pa: {
          male: 'ਮਰਦ',
          female: 'ਔਰਤ',
        },
    raj: {
          male: 'पुरुष',
          female: 'महिला',
        },
    ta: {
          male: 'ஆண்',
          female: 'பெண்',
        },
    te: {
          male: 'పురుషుడు',
          female: 'స్త్రీ',
        },
    ur: {
          male: 'مرد',
          female: 'خاتون',
        }
        // Add more language translations as needed
      },

  format: 'wav'
};

// Function to check if a specific feature is supported in a language
export const isLanguageSupported = (languageCode, feature = 'all') => {
  const language = SUPPORTED_LANGUAGES[languageCode];
  if (!language) return false;
  
  if (feature === 'all') {
    return language.supported.tts && language.supported.stt && language.supported.translation;
  }
  
  return language.supported[feature] || false;
};

// Get language data by language code, defaults to 'en' if code not found
export const getLanguageData = (languageCode) => {
  return SUPPORTED_LANGUAGES[languageCode] || SUPPORTED_LANGUAGES[DEFAULT_LANGUAGE];
};

// Get direction for the selected language
export const getTextDirection = (languageCode) => {
  const language = getLanguageData(languageCode);
  return language.direction;
};


const translations = {
    en: {
      "Patient Details": "Patient Details",
      "Personal Information": "Personal Information",
      "First Name": "First Name",
      "Last Name": "Last Name",
      "Age": "Age",
      "Gender": "Gender",
      "Male": "Male",           // Added
      "Female": "Female",       // Added
      "Other": "Other",
      "Height (cm)": "Height (cm)",
      "Weight (kg)": "Weight (kg)",
      "Email": "Email ID",
      "Mobile Number": "Mobile Number",
      "Language Preferences": "Select Language",
      "Preferred Language": "Preferred Language",
      "Voice Preferences": "Voice Preferences",
      "Enable Voice Output": "Enable Voice Output",
      "Voice Gender": "Voice Gender",
      "Voice Speed": "Voice Speed",
      "Submit": "Submit"
    },
    
    hi: {
      "Patient Details": "मरीज़ का विवरण",
      "Personal Information": "व्यक्तिगत जानकारी",
      "First Name": "पहला नाम",
      "Last Name": "अंतिम नाम",
      "Age": "आयु",
      "Gender": "लिंग",
      "Height (cm)": "लंबाई (से.मी.)",
      "Weight (kg)": "वजन (किलोग्राम)",
      "Email": "ईमेल आईडी",
      "Mobile Number": "मोबाइल नंबर",
      "Language Preferences": "भाषा चयन करें",
      "Preferred Language": "पसंदीदा भाषा",
      "Voice Preferences": "स्वर चयन",
      "Enable Voice Output": "स्वर आउटपुट सक्षम करें",
      "Voice Gender": "स्वर का लिंग",
      "Voice Speed": "स्वर गति",
      "Submit": "जमा करें"
    },

    as:{
      "Patient Details": "ৰোগী বিবৰণ",
      "Personal Information": "ব্যক্তিগত তথ্য",
      "First Name": "প্ৰথম নাম",
      "Last Name": "শেষ নাম",
      "Age": "বয়স",
      "Gender": "লিংগ",
      "Height (cm)": "উচ্চতা (সেমি)",
      "Weight (kg)": "ওজন (কেজি)",
      "Email": "ই-মেইল আইডি",
      "Mobile Number": "মোবাইল নম্বৰ",
      "Language Preferences": "ভাষা বাচনি",
      "Preferred Language": "পছন্দৰ ভাষা",
      "Voice Preferences": "স্বৰ বাচনি",
      "Enable Voice Output": "স্বৰ আউটপুট সক্ৰিয় কৰক",
      "Voice Gender": "স্বৰৰ লিংগ",
      "Voice Speed": "স্বৰৰ গতি",
      "Submit": "জমা কৰক"
    },
  
    bn: {
      "Patient Details": "রোগী বিস্তারিত",
      "Personal Information": "ব্যক্তিগত তথ্য",
      "First Name": "প্রথম নাম",
      "Last Name": "শেষ নাম",
      "Age": "বয়স",
      "Gender": "লিঙ্গ",
      "Height (cm)": "উচ্চতা (সেমি)",
      "Weight (kg)": "ওজন (কেজি)",
      "Email": "ইমেইল আইডি",
      "Mobile Number": "মোবাইল নম্বর",
      "Language Preferences": "ভাষা পছন্দ",
      "Preferred Language": "পছন্দের ভাষা",
      "Voice Preferences": "স্বাক্ষর পছন্দ",
      "Enable Voice Output": "ভয়েস আউটপুট সক্রিয় করুন",
      "Voice Gender": "স্বাক্ষরের লিঙ্গ",
      "Voice Speed": "স্বাক্ষরের গতি",
      "Submit": "জমা দিন"
    },

    br: {
      'Patient Details': 'रोगी का विवरण',
      'Personal Information': 'व्यक्तिगत जानकारी',
      'First Name': 'पहला नाम',
      'Last Name': 'अंतिम नाम',
      'Age': 'उम्र',
      'Gender': 'लिंग',
      'Height (cm)': 'ऊंचाई (सेमी)',
      'Weight (kg)': 'वजन (किग्रा)',
      'Email': 'ईमेल',
      'Mobile Number': 'मोबाइल नंबर',
      'Language Preferences': 'भाषा की प्राथमिकताएँ',
      'Preferred Language': 'पसंदीदा भाषा',
      'Voice Preferences': 'वॉइस प्राथमिकताएँ',
      'Enable Voice Output': 'वॉइस आउटपुट सक्षम करें',
      'Voice Gender': 'वॉइस जेंडर',
      'Voice Speed': 'वॉइस गति',
      'Submit': 'प्रस्तुत'
    },
    gu: {
      'Patient Details': 'રોગી વિગતો',
      'Personal Information': 'વ્યક્તિગત માહિતી',
      'First Name': 'પ્રથમ નામ',
      'Last Name': 'છેલ્લું નામ',
      'Age': 'ઉંમર',
      'Gender': 'લિંગ',
      'Height (cm)': 'ઊંચાઇ (સે.મી.)',
      'Weight (kg)': 'વજન (કિ.ગ્રા)',
      'Email': 'ઇમેલ',
      'Mobile Number': 'મોબાઇલ નંબર',
      'Language Preferences': 'ભાષા પસંદગીઓ',
      'Preferred Language': 'પસંદગીની ભાષા',
      'Voice Preferences': 'વોઇસ પસંદગીઓ',
      'Enable Voice Output': 'વોઇસ આઉટપુટ સક્ષમ કરો',
      'Voice Gender': 'વોઇસ લિંગ',
      'Voice Speed': 'વોઇસ સ્પીડ',
      'Submit': 'સબમિટ કરો'
    },
    kn: {
      'Patient Details': 'ರೋಗಿಯ ವಿವರಗಳು',
      'Personal Information': 'ವೈಯಕ್ತಿಕ ಮಾಹಿತಿ',
      'First Name': 'ಮೊದಲ ಹೆಸರು',
      'Last Name': 'ಕೊನೆಯ ಹೆಸರು',
      'Age': 'ವಯಸ್ಸು',
      'Gender': 'ಲಿಂಗ',
      'Height (cm)': 'ಎತ್ತರ (ಸೆಂ)',
      'Weight (kg)': 'ತೂಕ (ಕೆ.ಜಿ)',
      'Email': 'ಇಮೇಲ್',
      'Mobile Number': 'ಮೊಬೈಲ್ ನಂಬರ',
      'Language Preferences': 'ಭಾಷಾ ಆಯ್ಕೆ',
      'Preferred Language': 'ಆದರ್ಶ ಭಾಷೆ',
      'Voice Preferences': 'ವಾಯ್ಸ್ ಆಯ್ಕೆ',
      'Enable Voice Output': 'ವಾಯ್ಸ್ ಔಟ್‌ಪುಟ್ ಸಕ್ರಿಯಗೊಳಿಸಿ',
      'Voice Gender': 'ವಾಯ್ಸ್ ಲಿಂಗ',
      'Voice Speed': 'ವಾಯ್ಸ್ ವೇಗ',
      'Submit': 'ಸಲ್ಲಿಸಿ'
    },
    ml: {
      'Patient Details': 'രോഗിയുടെ വിശദാംശങ്ങൾ',
      'Personal Information': 'വ്യക്തിപരമായ വിവരങ്ങൾ',
      'First Name': 'ആദ്യ പേര്',
      'Last Name': 'അവസാന പേര്',
      'Age': 'വയസ്സ്',
      'Gender': 'ലിംഗം',
      'Height (cm)': 'ഉയരം (സെ.മീ)',
      'Weight (kg)': 'ഭാരം (കി.ഗ്ര)',
      'Email': 'ഇമെയിൽ',
      'Mobile Number': 'മൊബൈൽ നമ്പർ',
      'Language Preferences': 'ഭാഷാ തിരഞ്ഞെടുപ്പുകൾ',
      'Preferred Language': 'ആവശ്യപ്പെട്ട ഭാഷ',
      'Voice Preferences': 'വോയിസ് തിരഞ്ഞെടുപ്പുകൾ',
      'Enable Voice Output': 'വോയിസ് ഔട്ട്പുട്ട് പ്രവർത്തനക്ഷമമാക്കുക',
      'Voice Gender': 'വോയിസ് ലിംഗം',
      'Voice Speed': 'വോയിസ് സ്പീഡ്',
      'Submit': 'സമർപ്പിക്കുക'
    },
    mr: {
      'Patient Details': 'रुग्णाचा तपशील',
      'Personal Information': 'वैयक्तिक माहिती',
      'First Name': 'पहिले नाव',
      'Last Name': 'आडनाव',
      'Age': 'वय',
      'Gender': 'लिंग',
      'Height (cm)': 'उंची (सेमी)',
      'Weight (kg)': 'वजन (किलो)',
      'Email': 'ईमेल',
      'Mobile Number': 'मोबाईल नंबर',
      'Language Preferences': 'भाषा प्राधान्ये',
      'Preferred Language': 'प्राधान्यकृत भाषा',
      'Voice Preferences': 'वॉईस प्राधान्ये',
      'Enable Voice Output': 'वॉईस आऊटपुट सक्षम करा',
      'Voice Gender': 'वॉईस लिंग',
      'Voice Speed': 'वॉईस गती',
      'Submit': 'प्रस्तुत'
    },
    or: {
      'Patient Details': 'ରୋଗୀର ବିବରଣୀ',
      'Personal Information': 'ବ୍ୟକ୍ତିଗତ ତଥ୍ୟ',
      'First Name': 'ପ୍ରଥମ ନାମ',
      'Last Name': 'ଶେଷ ନାମ',
      'Age': 'ବୟସ',
      'Gender': 'ଲିଙ୍ଗ',
      'Height (cm)': 'ଉଚ୍ଚତା (ସେ.ମି.)',
      'Weight (kg)': 'ଭାର (କି.ଗ୍ରା)',
      'Email': 'ଇମେଲ',
      'Mobile Number': 'ମୋବାଇଲ ନମ୍ବର',
      'Language Preferences': 'ଭାଷା ପ୍ରାଥମିକତା',
      'Preferred Language': 'ପ୍ରାଥମିକତା ଭାଷା',
      'Voice Preferences': 'ଭୟସ ପ୍ରାଥମିକତା',
      'Enable Voice Output': 'ଭୟସ ଆଉଟପୁଟ ସକ୍ରିୟ କରନ୍ତୁ',
      'Voice Gender': 'ଭୟସ ଲିଙ୍ଗ',
      'Voice Speed': 'ଭୟସ ଗତି',
      'Submit': 'ଦାଖଲ'
    },
    pa: {
      'Patient Details': 'ਮਰੀਜ਼ ਦਾ ਵੇਰਵਾ',
      'Personal Information': 'ਨਿੱਜੀ ਜਾਣਕਾਰੀ',
      'First Name': 'ਪਹਿਲਾ ਨਾਮ',
      'Last Name': 'ਆਖਰੀ ਨਾਮ',
      'Age': 'ਉਮਰ',
      'Gender': 'ਲਿੰਗ',
      'Height (cm)': 'ਉਚਾਈ (ਸੈਮੀ)',
      'Weight (kg)': 'ਵਜ਼ਨ (ਕਿਲੋ)',
      'Email': 'ਈਮੇਲ',
      'Mobile Number': 'ਮੋਬਾਈਲ ਨੰਬਰ',
      'Language Preferences': 'ਭਾਸ਼ਾ ਦੀਆਂ ਪਸੰਦਾਂ',
      'Preferred Language': 'ਪਸੰਦੀਦਾ ਭਾਸ਼ਾ',
      'Voice Preferences': 'ਵੌਇਸ ਪਸੰਦਾਂ',
      'Enable Voice Output': 'ਵੌਇਸ ਆਉਟਪੁਟ ਨੂੰ ਯੋਗ ਕਰੋ',
      'Voice Gender': 'ਵੌਇਸ ਲਿੰਗ',
      'Voice Speed': 'ਵੌਇਸ ਦੀ ਰਫ਼ਤਾਰ',
      'Submit': 'ਜਮ੍ਹਾਂ ਕਰੋ'
    },
    ur: {
      'Patient Details': 'مریض کی تفصیلات',
      'Personal Information': 'ذاتی معلومات',
      'First Name': 'پہلا نام',
      'Last Name': 'آخری نام',
      'Age': 'عمر',
      'Gender': 'صنف',
      'Height (cm)': 'قد (سینٹی میٹر)',
      'Weight (kg)': 'وزن (کلو)',
      'Email': 'ای میل',
      'Mobile Number': 'موبائل نمبر',
      'Language Preferences': 'زبان کی ترجیحات',
      'Preferred Language': 'پسندیدہ زبان',
      'Voice Preferences': 'آواز کی ترجیحات',
      'Enable Voice Output': 'آواز کو فعال کریں',
      'Voice Gender': 'آواز کی جنس',
      'Voice Speed': 'آواز کی رفتار',
      'Submit': 'جمع کریں'
    }
    // Add translations for other languages as needed
  };

  // Helper to retrieve a translated language name if available
export const getLanguageName = (languageCode, key) => {
  // If no language code or key provided, return the key
  if (!languageCode || !key) return key;

  // Get translations for the selected language
  const languageTranslations = translations[languageCode];
  
  // If no translations found for the language or specific key, return the original key
  if (!languageTranslations || !languageTranslations[key]) {
    console.warn(`Translation missing for key "${key}" in language "${languageCode}"`);
    return key;
  }
  
  return languageTranslations[key];
};

