export const landingHeroDesign = {
  backgroundImage:
    'https://www.figma.com/api/mcp/asset/93deb18d-052b-42bc-b68f-213cbbc1aa15',
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
      'https://www.figma.com/api/mcp/asset/0d4451cf-1297-46c3-95e3-2bdfdbb75fc5',
      'https://www.figma.com/api/mcp/asset/7743ad10-0d81-4846-ba2f-45640d8c0f25',
      'https://www.figma.com/api/mcp/asset/e2854a88-4329-4bf6-97c0-b1c30c2b72c8',
      'https://www.figma.com/api/mcp/asset/081f8216-bcb3-41c2-8d12-038551e1ab53',
    ],
    extraAvatar:
      'https://www.figma.com/api/mcp/asset/48387098-4a6d-4bb0-985b-8bfa37a92b4e',
  },
  {
    id: 'practice',
    tone: 'dark',
    title: 'Изучай теорию и решай реальные кейсы. Никаких отговорок!',
    badgeTitle: '140 заданий',
    badgeSubtitle: 'на платформе',
    figureImage:
      'https://www.figma.com/api/mcp/asset/8b86fa47-d633-41f0-8557-9918bf9ea685',
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
      'https://www.figma.com/api/mcp/asset/101ef335-37bd-4f22-9197-8a73d726ffd5',
      'https://www.figma.com/api/mcp/asset/838dba51-8441-458e-a18c-ec64d5039fad',
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
        image: 'https://www.figma.com/api/mcp/asset/2fcca71c-da6c-4f31-9f2d-6e707732ca1e',
        className: 'landing-figma-slide-shot landing-figma-slide-shot--rear',
      },
      {
        image: 'https://www.figma.com/api/mcp/asset/ece28213-3d8f-4e27-9098-01ff2fbf4b68',
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
      'https://www.figma.com/api/mcp/asset/ff511c06-0495-4eef-8ca7-3a568be8126d',
  },
  {
    id: 'rating',
    tabLabel: 'Рейтинг',
    tagLabel: 'Рейтинг',
    title:
      'Обновляем после каждого нового турнира. Учитываем, кто первый нашел флаг, количество и сложность найденных флагов',
    composition: 'rating',
    panelImage:
      'https://www.figma.com/api/mcp/asset/26e140bb-42c5-41f7-afb8-aa5ad23105ad',
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
      'https://www.figma.com/api/mcp/asset/e406cfd3-3ed3-43d9-a8a2-b8756725d91f',
    hintPopup: {
      imageOne:
        'https://www.figma.com/api/mcp/asset/56e45b2a-4510-4dbb-8f82-45ebb3360614',
      imageTwo:
        'https://www.figma.com/api/mcp/asset/016c6b8f-7d78-4a2d-9ff5-a558f2eb8345',
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
      'https://www.figma.com/api/mcp/asset/0671eedf-da00-43f0-a836-fcd7591c1e61',
    backLabel: 'Практика',
    backImage:
      'https://www.figma.com/api/mcp/asset/ca40309a-af16-46a4-9451-fa1d420615a4',
  },
  {
    id: 'practice',
    title: 'Практика',
    body:
      'Здесь ты решаешь задачи и готовишься к реальным вызовам в мире кибербезопасности. Проходить их можно в треке теории или отдельно',
    cardTone: 'light',
    frontLabel: 'Практика',
    frontImage:
      'https://www.figma.com/api/mcp/asset/ca40309a-af16-46a4-9451-fa1d420615a4',
    backLabel: 'Теория',
    backImage:
      'https://www.figma.com/api/mcp/asset/0671eedf-da00-43f0-a836-fcd7591c1e61',
  },
];

export const landingLearningPanel = {
  title:
    'За прохождение модулей и задач получай баллы, соревнуйся с другими участниками и повышай свои компетенции',
  glowImage: 'https://www.figma.com/api/mcp/asset/23cdc6e7-4f5e-42ea-9819-a7e4d731daf3',
  decorImage:
    'https://www.figma.com/api/mcp/asset/24f5d06e-24f9-4729-baad-63f8588ca88e',
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
        image: 'https://www.figma.com/api/mcp/asset/e8627aee-a67f-48f2-b068-d62f5ebf39b3',
      },
      {
        title: 'Пошаговое обучение на реальных кейсах',
        body:
          'Освой основы кибербезопасности по практическим модулям, чтобы сразу понимать, как все работает в реальной жизни',
        tone: 'dark',
        image: 'https://www.figma.com/api/mcp/asset/e2b3aff9-09cd-48d4-9667-95a7e9cf4954',
      },
      {
        title: 'Регулярно обновляемая База знаний',
        body:
          'Следи за важными изменениями и актуальными подходами к хакингу. WriteUps от пользователей, новости и тренды — все для твоего профессионального роста!',
        tone: 'blue',
        image: 'https://www.figma.com/api/mcp/asset/021e5397-e71b-451a-829d-ed71b4aa3429',
      },
      {
        title: 'Практика с заданиями разных уровней',
        body:
          'Начни с простых задач и постепенно переходи к более сложным, улучшая свои навыки шаг за шагом',
        tone: 'dark',
        image: 'https://www.figma.com/api/mcp/asset/95f662ed-589c-4930-9335-1268fb51af8d',
      },
      {
        title: 'Отслеживание прогресса',
        body:
          'Следи за успехами в дашборде, прокачивай навыки и соревнуйся в обучении с другими пользователями',
        tone: 'violet',
        image: 'https://www.figma.com/api/mcp/asset/daf6cf08-c2e0-449b-92e3-a68cf1568810',
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
        image: 'https://www.figma.com/api/mcp/asset/3f94561b-1ab2-4d74-88a8-a13f28be547a',
      },
      {
        title: 'Повышение компетенций в конкретной категории знаний',
        body:
          'Изучай актуальные решения хакеров платформы в Базе знаний, проходи модули и выполняй задания из определенной категории кибербезопасности, а мы отследим твой прогресс',
        tone: 'dark',
        image: 'https://www.figma.com/api/mcp/asset/ec83ee64-0a2d-4e69-99f5-6ac409e4f196',
      },
      {
        title: 'Регулярные турниры с практическими задачами',
        body:
          'Каждую неделю ты можешь проверить свои навыки на новых заданиях, которые имитируют реальные ситуации. Если оказалось слишком сложно — учись на решениях, которые мы публикуем в Базе знаний после завершения турнира',
        tone: 'blue',
        image: 'https://www.figma.com/api/mcp/asset/4691bbb6-cb21-474a-93d4-d1a9b1fa4048',
      },
      {
        title: 'Аналитика прохождения турниров',
        body:
          'После каждого турнира мы даем детализированную аналитику: где ты застрял, сколько времени потратил и какие флаги были наиболее сложными. Это поможет выявить слабые места и сформировать трек развития',
        tone: 'dark',
        image: 'https://www.figma.com/api/mcp/asset/42636db9-c443-4613-ad09-062d6936ef56',
        locked: true,
      },
      {
        title: 'Возможность формировать задачи под себя',
        body:
          'Уже решил все практические задания на платформе или они оказались слишком простыми? Сгенерируй уникальные задачи под свой уровень компетенций',
        tone: 'violet',
        image: 'https://www.figma.com/api/mcp/asset/89fab7b3-ac94-4725-9341-963b9fa99ca2',
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
  'https://www.figma.com/api/mcp/asset/dcbc1243-2c63-40e3-ba44-9469e32ee428';

export const landingPromoModalAssets = {
  backdrop: 'https://www.figma.com/api/mcp/asset/74990863-1dad-4e55-8045-f7b291a0d9a6',
};
