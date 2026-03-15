import React, { useEffect } from 'react';

import { LandingFooter, LandingHeader } from '../components/landing/LandingChrome';
import { getLegalDocument } from '../lib/landingConfig';

function LegalSection({ heading, paragraphs }) {
  return (
    <section className="space-y-4">
      <h2 className="text-[24px] leading-[30px] tracking-[0.02em] text-white">{heading}</h2>
      <div className="space-y-3 text-[16px] leading-[28px] tracking-[0.02em] text-white/74">
        {paragraphs.map((paragraph) => (
          <p key={paragraph}>{paragraph}</p>
        ))}
      </div>
    </section>
  );
}

export default function LandingLegal({ documentKey = 'privacy' }) {
  const legalDocument = getLegalDocument(documentKey);

  useEffect(() => {
    window.scrollTo(0, 0);
    window.document.title = `${legalDocument.title} | HackNet`;
  }, [legalDocument.title]);

  return (
    <div className="landing-page-bg min-h-screen font-sans-figma text-white">
      <LandingHeader mode="legal" currentLegalKey={legalDocument.key} />

      <main className="relative overflow-hidden">
        <div className="absolute inset-x-0 top-0 h-[360px] bg-[radial-gradient(circle_at_top,_rgba(123,87,249,0.24),_rgba(9,8,13,0)_68%)]" />
        <div className="relative mx-auto flex max-w-[1040px] flex-col gap-10 px-4 pb-20 pt-14 sm:px-6 lg:pb-24 lg:pt-20">
          <section className="landing-surface-lg">
            <div className="space-y-4">
              <span className="inline-flex rounded-full border border-white/[0.08] bg-white/[0.04] px-4 py-2 text-[12px] uppercase tracking-[0.22em] text-white/54">
                Юридические документы
              </span>
              <h1 className="max-w-[760px] text-[34px] leading-[40px] tracking-[-0.03em] text-white sm:text-[42px] sm:leading-[48px] lg:text-[56px] lg:leading-[60px]">
                {legalDocument.title}
              </h1>
              <p className="max-w-[760px] text-[18px] leading-[30px] tracking-[0.02em] text-white/64">
                {legalDocument.subtitle}
              </p>
            </div>
          </section>

          <article className="landing-surface-lg flex flex-col gap-10">
            {legalDocument.sections.map((section) => (
              <LegalSection
                key={section.heading}
                heading={section.heading}
                paragraphs={section.paragraphs}
              />
            ))}
          </article>
        </div>
      </main>

      <LandingFooter currentLegalKey={legalDocument.key} />
    </div>
  );
}
