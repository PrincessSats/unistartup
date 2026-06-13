import {
  LANDING_PLACEHOLDER_IMAGE,
  LANDING_PLACEHOLDER_AVATAR,
  LANDING_PLACEHOLDER_HERO,
} from './landingPlaceholders';

export const landingHeroDesign = {
  backgroundImage:
    LANDING_PLACEHOLDER_HERO,
  eyebrow: 'HackNet',
  title: 'Соревнуйся с лучшими, развивайся и тренируй команду!',
  subtitle: 'для новичков и опытных специалистов',
  cookies:
    'Мы используем cookies, чтобы улучшать платформу, персонализировать контент и безопасно сохранять состояние интерактивов.',
};

export const landingBenefitCards = [
  {
    id: 'championships',
    tone: 'violet',
    title: 'Регулярные чемпионаты — прокачивай навыки в боевых условиях',
    participantsLabel: 'хакеров участвует',
    participantsValue: '+132',
    participantAvatars: [
      LANDING_PLACEHOLDER_AVATAR,
      LANDING_PLACEHOLDER_AVATAR,
      LANDING_PLACEHOLDER_AVATAR,
      LANDING_PLACEHOLDER_AVATAR,
    ],
    extraAvatar:
      LANDING_PLACEHOLDER_AVATAR,
  },
  {
    id: 'practice',
    tone: 'dark',
    title: 'Изучай теорию и решай реальные кейсы. Никаких отговорок!',
    badgeTitle: '140 заданий',
    badgeSubtitle: 'на платформе',
    figureImage:
      LANDING_PLACEHOLDER_IMAGE,
  },
  {
    id: 'progress',
    tone: 'blue',
    title: 'Следи за прогрессом',
    description: 'Фиксируем твои достижения и подскажем, что с ними делать дальше',
    stats: [
      { value: '174', delta: '-1', deltaTone: 'down', label: 'Рейтинг' },
      { value: '2328', delta: '+4', deltaTone: 'up', label: 'Очки' },
    ],
  },
  {
    id: 'levels',
    tone: 'light',
    title: 'Задачи для всех: от новичков до профи',
    description: 'Выбирай свой уровень и ломай голову',
    figureImages: [
      LANDING_PLACEHOLDER_IMAGE,
      LANDING_PLACEHOLDER_IMAGE,
    ],
  },
];

export const landingChampionshipSlides = [
  {
    id: 'flow',
    tabLabel: 'Как проводим',
    tagLabel: 'Как проводим',
    title:
      'Публикуем задание на платформе. В отведенное время ищи флаги и вписывай в поле ответа — из результатов формируем рейтинговую таблицу. Пока участвовать можно только одному, но мы уже работаем над командным форматом',
    composition: 'flow',
    panelLayers: [
      {
        image: LANDING_PLACEHOLDER_IMAGE,
        className: 'landing-figma-slide-shot landing-figma-slide-shot--rear',
      },
      {
        image: LANDING_PLACEHOLDER_IMAGE,
        className: 'landing-figma-slide-shot landing-figma-slide-shot--front',
      },
    ],
  },
  {
    id: 'formats',
    tabLabel: 'Форматы заданий',
    tagLabel: 'Форматы заданий',
    title: 'Миксуем форматы заданий для развития более комплексных и универсальных навыков',
    composition: 'formats',
    badges: ['Виртуальные машины', 'Файлы для анализа', 'Веб-страницы', 'Удаленные серверы'],
    panelImage:
      LANDING_PLACEHOLDER_IMAGE,
  },
  {
    id: 'rating',
    tabLabel: 'Рейтинг',
    tagLabel: 'Рейтинг',
    title:
      'Обновляем после каждого нового турнира. Учитываем, кто первый нашел флаг, количество и сложность найденных флагов',
    composition: 'rating',
    panelImage:
      LANDING_PLACEHOLDER_IMAGE,
    floatingScore: {
      place: '8141',
      user: 'CyberNinja',
      score: '12',
      firstBlood: '0',
      solved: '0',
    },
  },
  {
    id: 'fallback',
    tabLabel: 'Что, если я не решу',
    tagLabel: 'Что, если я не решу',
    title:
      'Если сложно решить турнирное задание - сформируем план обучения под нужную область знаний. После завершения турнира выкладываем решения по поиску флагов',
    composition: 'fallback',
    panelImage:
      LANDING_PLACEHOLDER_IMAGE,
    hintPopup: {
      imageOne:
        LANDING_PLACEHOLDER_IMAGE,
      imageTwo:
        LANDING_PLACEHOLDER_IMAGE,
      title: 'Не беда - потренируйся на похожих заданиях',
      body: 'Отобрали задания такой же категории и сложности в разделе «Обучение»',
      action: 'Тренироваться',
    },
  },
];

export const landingLearningCards = [
  {
    id: 'theory',
    title: 'Теория',
    body:
      'Здесь ты изучаешь базу и продвинутые концепции кибербезопасности. Модули построены на реальных примерах, чтобы ты мог применить знания в работе',
    cardTone: 'light',
    frontLabel: 'Теория',
    frontImage:
      LANDING_PLACEHOLDER_IMAGE,
    backLabel: 'Практика',
    backImage:
      LANDING_PLACEHOLDER_IMAGE,
  },
  {
    id: 'practice',
    title: 'Практика',
    body:
      'Здесь ты решаешь задачи и готовишься к реальным вызовам в мире кибербезопасности. Проходить их можно в треке теории или отдельно',
    cardTone: 'light',
    frontLabel: 'Практика',
    frontImage:
      LANDING_PLACEHOLDER_IMAGE,
    backLabel: 'Теория',
    backImage:
      LANDING_PLACEHOLDER_IMAGE,
  },
];

export const landingLearningPanel = {
  title:
    'За прохождение модулей и задач получай баллы, соревнуйся с другими участниками и повышай свои компетенции',
  glowImage: LANDING_PLACEHOLDER_IMAGE,
  decorImage:
    LANDING_PLACEHOLDER_IMAGE,
  toastTitle: 'Модуль пройден!',
  toastBody: 'Уже начислили очки в твой рейтинг',
};

export const landingAudienceTabs = [
  {
    id: 'junior',
    label: 'Новичок',
    cards: [
      {
        title: 'Рекомендации на старте',
        body:
          'Выполни одну тестовую задачу, чтобы мы оценили твой текущий уровень, и получи трек развития на основе твоих интересов',
        tone: 'violet',
        image: LANDING_PLACEHOLDER_IMAGE,
      },
      {
        title: 'Пошаговое обучение на реальных кейсах',
        body:
          'Освой основы кибербезопасности по практическим модулям, чтобы сразу понимать, как все работает в реальной жизни',
        tone: 'dark',
        image: LANDING_PLACEHOLDER_IMAGE,
      },
      {
        title: 'Регулярно обновляемая База знаний',
        body:
          'Следи за важными изменениями и актуальными подходами к хакингу. WriteUps от пользователей, новости и тренды — все для твоего профессионального роста!',
        tone: 'blue',
        image: LANDING_PLACEHOLDER_IMAGE,
      },
      {
        title: 'Практика с заданиями разных уровней',
        body:
          'Начни с простых задач и постепенно переходи к более сложным, улучшая свои навыки шаг за шагом',
        tone: 'dark',
        image: LANDING_PLACEHOLDER_IMAGE,
      },
      {
        title: 'Отслеживание прогресса',
        body:
          'Следи за успехами в дашборде, прокачивай навыки и соревнуйся в обучении с другими пользователями',
        tone: 'violet',
        image: LANDING_PLACEHOLDER_IMAGE,
      },
    ],
  },
  {
    id: 'pro',
    label: 'Опытный специалист',
    cards: [
      {
        title: 'Рейтинг лучших хакеров',
        body:
          'Получай очки первой крови за турниры, зарабатывай баллы за практические задания и повышай свою позицию в рейтинге среди профессионалов. А мы гарантируем честное формирование турнирной таблицы',
        tone: 'violet',
        image: LANDING_PLACEHOLDER_IMAGE,
      },
      {
        title: 'Повышение компетенций в конкретной категории знаний',
        body:
          'Изучай актуальные решения хакеров платформы в Базе знаний, проходи модули и выполняй задания из определенной категории кибербезопасности, а мы отследим твой прогресс',
        tone: 'dark',
        image: LANDING_PLACEHOLDER_IMAGE,
      },
      {
        title: 'Регулярные турниры с практическими задачами',
        body:
          'Каждую неделю ты можешь проверить свои навыки на новых заданиях, которые имитируют реальные ситуации. Если оказалось слишком сложно — учись на решениях, которые мы публикуем в Базе знаний после завершения турнира',
        tone: 'blue',
        image: LANDING_PLACEHOLDER_IMAGE,
      },
      {
        title: 'Аналитика прохождения турниров',
        body:
          'После каждого турнира мы даем детализированную аналитику: где ты застрял, сколько времени потратил и какие флаги были наиболее сложными. Это поможет выявить слабые места и сформировать трек развития',
        tone: 'dark',
        image: LANDING_PLACEHOLDER_IMAGE,
        locked: true,
      },
      {
        title: 'Возможность формировать задачи под себя',
        body:
          'Уже решил все практические задания на платформе или они оказались слишком простыми? Сгенерируй уникальные задачи под свой уровень компетенций',
        tone: 'violet',
        image: LANDING_PLACEHOLDER_IMAGE,
        locked: true,
      },
    ],
  },
];

export const landingFaqItems = [
  {
    question: 'В чем отличие турниров и практики',
    answer:
      'Турниры идут в ограниченное время и собирают общий рейтинг по поиску флагов. Практика доступна в удобном темпе и помогает закрывать конкретные пробелы между соревнованиями.',
  },
  {
    question: 'Как обучение связано с практикой',
    answer:
      'После каждого теоретического модуля тебя ждут боевые задания, а сложные темы можно сразу закрепить в практическом треке без ожидания следующего турнира.',
  },
  {
    question: 'Что такое База знаний',
    answer:
      'Это библиотека WriteUp, обновлений, разборов решений и материалов по категориям кибербезопасности. Она помогает быстро вернуться к нужной теме и усилить слабые места.',
  },
  {
    question: 'Кто проверяет правильность выполнения заданий',
    answer:
      'Платформа валидирует флаги автоматически, а логика турниров и материалов собирается и модерируется командой HackNet, чтобы рейтинг формировался честно.',
  },
  {
    question: 'Какие задания мне предстоит выполнять',
    answer:
      'На платформе есть веб-задачи, анализ файлов, форензика, OSINT, реверс-инжиниринг и другие форматы. Набор зависит от выбранного трека и твоего уровня.',
  },
  {
    question: 'Какой уровень подготовки требуется для начала',
    answer:
      'Стартовать можно и без турнирного опыта: мы рекомендуем сначала пройти тестовое задание и получить трек развития. Дальше сложность можно наращивать постепенно.',
  },
  {
    question: 'Как долго длится обучение',
    answer:
      'Обучение не ограничено одной программой. Можно проходить модули в удобном ритме, а турнирные активности подключать тогда, когда готов соревноваться.',
  },
  {
    question: 'Что будет, если я не смогу решить задание в срок',
    answer:
      'После завершения турнира открываются разборы и решения, а для сложных тем платформа предложит похожие задания и маршрут обучения по нужной категории.',
  },
];

export const landingWaitlistCloud = [
  { label: 'тренировочный центр', left: '5.3%', top: '7%' },
  { label: 'виртуальные машины', left: '23.9%', top: '11.8%' },
  { label: 'прогресс компетенций', left: '14.8%', top: '17.4%' },
  { label: 'чемпионаты', left: '51.5%', top: '13.2%' },
  { label: 'реальные кейсы', left: '74.6%', top: '9.6%' },
  { label: 'фиксируем прогресс', left: '89.2%', top: '17.5%' },
  { label: 'план обучения', left: '95.4%', top: '21.4%' },
  { label: 'честный рейтинг', left: '91.1%', top: '29.3%' },
  { label: 'Writeups', left: '12.3%', top: '43.5%' },
  { label: 'балльная система', left: '5.2%', top: '50.1%' },
  { label: 'поиск флагов', left: '91.5%', top: '69.6%' },
  { label: 'рекомендации на старте', left: '3.6%', top: '74.5%' },
  { label: 'белые хакеры', left: '23.1%', top: '72.7%' },
  { label: 'все уровни сложности', left: '96%', top: '79.2%' },
  { label: 'сообщество профессионалов', left: '30.8%', top: '86.6%' },
  { label: 'разные категории знаний', left: '89.6%', top: '89.7%' },
  { label: 'интеллектуальный спорт', left: '6.2%', top: '92.7%' },
  { label: 'База знаний', left: '59.7%', top: '95.5%' },
];

export const landingTrackerIcon =
  LANDING_PLACEHOLDER_IMAGE;

export const landingPromoModalAssets = {
  backdrop: LANDING_PLACEHOLDER_IMAGE,
};
