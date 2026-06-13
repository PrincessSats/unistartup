// Сцены по сценарию (см. script.txt). Два клипа:
//   1) login — показ страницы входа
//   2) tour  — единый авторизованный проход с плавными зумами, навигацией по
//              боковому меню и поясняющими подписями.
// Селекторы (русский интерфейс прода) собраны здесь. Каждый шаг обёрнут в safe(),
// поэтому отсутствующий элемент пропускается, а не валит весь тур.

import * as h from './lib/human.js';

// Выполнить шаг; один сломанный селектор не должен прерывать весь тур.
async function safe(label, fn) {
  try {
    await fn();
  } catch (e) {
    console.log(`    [пропуск ${label}] ${e.message.split('\n')[0]}`);
  }
}

export function buildScenes(env) {
  const base = env.base;

  return [
    // ---- 1. ВХОД -----------------------------------------------------------
    {
      id: '01-login',
      route: '/login',
      requiresAuth: false,
      doLogin: true,
      async actions(page) {
        await h.caption(page, 'Welcome to HackNet', 'The hands-on cybersecurity learning platform');
        await h.dwell(1400);
        await safe('zoom-login', async () => {
          await h.zoomToPoint(page, 960, 470, 1.25, 1100);
          await h.dwell(1400);
          await h.zoomReset(page, 900);
        });
        await h.dwell(600);
      },
    },

    // ---- 2. ЕДИНЫЙ ТУР -----------------------------------------------------
    {
      id: '02-tour',
      route: '/home',
      requiresAuth: true,
      async actions(page) {
        await h.dismissOverlays(page);

        // --- ГЛАВНАЯ: дашборд / рейтинг -------------------------------------
        await safe('home-top', async () => {
          await h.caption(page, 'Your dashboard', 'Rank, points and progress — your at-a-glance overview');
          await h.dwell(1200);
          // верхняя панель героя показывается целиком
          const hero = page.getByText('Привет').first();
          await h.zoomToFit(page, hero, { maxScale: 1.3, dwell: 1900 });
          await h.zoomReset(page, 900);
        });

        // --- ГЛАВНАЯ: персональные задачи -----------------------------------
        await safe('home-tasks', async () => {
          const heading = page.getByText('Обучение под мои интересы').first();
          await h.caption(page, 'Tailored challenges', 'Labs picked for you, based on your interests');
          // панель задач показывается полностью
          await h.zoomToFit(page, heading, { maxScale: 1.25, dwell: 2000 });
          await h.zoomReset(page, 900);
        });

        // --- ГЛАВНАЯ: новости / новые задачи --------------------------------
        await safe('home-news', async () => {
          const news = page.getByText('Новости').first();
          await h.caption(page, 'Stay in the loop', 'Latest news, fresh CVEs and new tasks');
          // панель новостей в кадре целиком
          await h.zoomToFit(page, news, { maxScale: 1.25, dwell: 2000 });
          await h.zoomReset(page, 900);
          await h.smoothScroll(page, -1400, { steps: 45 });
          await h.dwell(500);
        });

        // --- ЧЕМПИОНАТ ------------------------------------------------------
        await safe('contest-nav', async () => {
          await h.caption(page, 'Live contests', 'Compete in timed competitions');
          await h.gotoViaSidebar(page, { base, label: 'Чемпионат', route: '/championship' });
        });
        await safe('contest-detail', async () => {
          await h.caption(page, 'Everything in one place', 'Schedule, description and tasks — all here');
          // описание чемпионата целиком
          const title = page.locator('h1, h2').first();
          await h.zoomToFit(page, title, { maxScale: 1.3, dwell: 1800 });
          await h.zoomReset(page, 800);
          await h.smoothScroll(page, 360);
          await h.dwell(1400);
          await h.smoothScroll(page, -360, { steps: 35 });
        });

        // --- ОБУЧЕНИЕ -------------------------------------------------------
        await safe('edu-nav', async () => {
          await h.caption(page, 'Hands-on learning', 'A deep library of CTF challenges');
          await h.gotoViaSidebar(page, { base, label: 'Обучение', route: '/education' });
          await h.dwell(1200);
        });

        let openedTask = false;
        await safe('edu-open-task', async () => {
          const card = page.locator('a[href*="/education/"]').first();
          await h.clickEl(page, card);
          await page.waitForLoadState('networkidle').catch(() => {});
          await h.dwell(1600);
          openedTask = true;
        });

        if (openedTask) {
          await safe('edu-task-detail', async () => {
            await h.caption(page, 'Pick a challenge', 'Read the brief, then launch the lab');
            // название и описание задачи целиком
            const title = page.locator('h1, h2').first();
            await h.zoomToFit(page, title, { maxScale: 1.3, dwell: 1800 });
            await h.zoomReset(page, 800);
          });
          await safe('edu-start', async () => {
            const start = page.locator('button:has-text("Начать"), a:has-text("Начать")').first();
            if (await start.isVisible().catch(() => false)) {
              await h.clickEl(page, start);
              await h.dwell(1400);
            }
          });
          await safe('edu-variants', async () => {
            const variants = page.getByText('Варианты от участников').first();
            await h.caption(page, 'Community variants', 'Players craft and share their own versions');
            // панель вариантов целиком
            await h.zoomToFit(page, variants, { maxScale: 1.3, dwell: 1800 });
            await h.zoomReset(page, 800);
          });
          await safe('edu-create', async () => {
            const create = page.locator('button:has-text("Создать"), a:has-text("Создать")').first();
            if (await create.isVisible().catch(() => false)) {
              await h.caption(page, 'Make your own', 'Define a brand-new task to share with everyone');
              await h.clickEl(page, create);
              await h.dwell(1800);
              // закрыть форму создания UGC после показа
              await h.closeModal(page);
              await h.dwell(700);
            }
          });
        }

        // --- РЕЙТИНГ --------------------------------------------------------
        await safe('rating-nav', async () => {
          await h.caption(page, 'Leaderboards', 'See where you stand');
          await h.gotoViaSidebar(page, { base, label: 'Рейтинг', route: '/rating' });
        });
        await safe('rating-detail', async () => {
          await h.caption(page, 'Two boards', 'Separate rankings for contests and training');
          // верхний блок рейтинга (две вкладки) целиком
          const top = page.locator('h1, h2').first();
          await h.zoomToFit(page, top, { maxScale: 1.25, dwell: 1800 });
          await h.zoomReset(page, 800);
        });

        // --- БАЗА ЗНАНИЙ ----------------------------------------------------
        await safe('kb-nav', async () => {
          await h.caption(page, 'Knowledge base', 'A living feed of vulnerabilities');
          await h.gotoViaSidebar(page, { base, label: 'База знаний', route: '/knowledge' });
          await h.dwell(1200);
        });
        await safe('kb-digest', async () => {
          await h.caption(page, 'Daily CVE digests', 'New CVEs gathered daily and compressed into one digest');
          // карточка свежего дайджеста целиком
          const card = page.locator('a[href*="/knowledge/"]').first();
          await h.zoomToFit(page, card, { maxScale: 1.3, dwell: 2000 });
          await h.zoomReset(page, 800);
        });

        // --- ОТКРЫТЬ ДАЙДЖЕСТ -----------------------------------------------
        await safe('kb-open', async () => {
          const card = page.locator('a[href*="/knowledge/"]').first();
          await h.clickEl(page, card);
          await page.waitForLoadState('networkidle').catch(() => {});
          await h.dwell(1600);
          await h.caption(page, 'Inside a digest', 'Every new CVE — linked, described and ready to study');
          await h.smoothScroll(page, 520);
          await h.dwell(1600);
          await h.smoothScroll(page, 520);
          await h.dwell(1600);
        });

        await h.hideCaption(page);
        await h.dwell(700);
      },
    },
  ];
}
