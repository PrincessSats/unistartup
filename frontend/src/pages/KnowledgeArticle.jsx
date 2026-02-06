import React, { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { knowledgeAPI } from '../services/api';

const heroGlass = 'https://www.figma.com/api/mcp/asset/83ec0217-d927-43dc-8152-7806866a3c5b';
const panelGlass = 'https://www.figma.com/api/mcp/asset/3a49cdeb-e88b-4e55-802a-766906beba34';
const eyeIcon = 'https://www.figma.com/api/mcp/asset/a348367d-ce0d-41b5-a110-8518938db3c4';
const arrowLeftIcon = 'https://www.figma.com/api/mcp/asset/819d79fe-8cdb-4999-9b58-0fa5de207ba1';

const heroGradient =
  'linear-gradient(86.51923569753619deg, rgb(86, 59, 166) 1.2823%, rgb(87, 56, 158) 15.301%, rgb(89, 60, 158) 35.395%, rgb(131, 89, 221) 62.966%, rgb(159, 99, 255) 98.48%)';

const tagGradients = {
  Web: 'linear-gradient(234.59deg, #7177CB 20.12%, #4049C7 100%)',
  OSINT: 'linear-gradient(234.59deg, #5B3CA8 20.12%, #2B2B3A 100%)',
  Криптография: 'linear-gradient(234.59deg, #6B4AC9 20.12%, #2C367F 100%)',
  Форензика: 'linear-gradient(234.59deg, #4E7C19 20.12%, #1B1B24 100%)',
  default: 'linear-gradient(234.59deg, #7177CB 20.12%, #4049C7 100%)',
};

function formatDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleDateString('ru-RU', { day: '2-digit', month: 'short', year: 'numeric' });
}

function formatCommentDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleDateString('ru-RU', { day: '2-digit', month: 'short', year: 'numeric' });
}

function estimateReadTime(text) {
  if (!text) return 3;
  const words = text.trim().split(/\s+/).length;
  return Math.max(1, Math.round(words / 160));
}

function getEntryTitle(entry) {
  return entry?.ru_title || entry?.cve_id || entry?.source_id || 'Без названия';
}

function RelatedCard({ entry }) {
  const tags = Array.isArray(entry?.tags) ? entry.tags : [];
  const primaryTag = tags[0];
  const secondaryTag = tags[1];
  const gradient = tagGradients[primaryTag] || tagGradients.default;

  return (
    <Link
      to={`/knowledge/${entry.id}`}
      className="group rounded-[16px] border border-white/[0.06] bg-[#0F0F14] transition hover:border-[#9B6BFF]/60"
    >
      <div
        className="relative h-[268px] overflow-hidden rounded-[16px]"
        style={{ backgroundImage: gradient }}
      >
        <img
          src={panelGlass}
          alt=""
          aria-hidden="true"
          className="absolute -left-10 top-3 h-[315px] w-[554px] opacity-90"
        />
      </div>
      <div className="flex flex-col gap-6 px-8 py-6">
        <div className="flex flex-wrap items-center justify-between gap-4 text-[14px] text-white/60">
          <div className="flex flex-wrap items-center gap-3">
            <span className="inline-flex items-center gap-1">
              <img src={eyeIcon} alt="" className="h-3.5 w-3.5" />
              {entry?.views ?? 0}
            </span>
            {primaryTag && (
              <span className="rounded-[10px] border border-[#8E51FF]/30 bg-[#8E51FF]/10 px-[13px] py-[9px] text-[16px] tracking-[0.64px] text-[#A684FF]">
                {primaryTag}
              </span>
            )}
            {secondaryTag && (
              <span className="rounded-[10px] border border-[#8E51FF]/30 bg-[#8E51FF]/10 px-[13px] py-[9px] text-[16px] tracking-[0.64px] text-[#A684FF]">
                {secondaryTag}
              </span>
            )}
          </div>
          <span className="text-white/50">{formatDate(entry?.created_at)}</span>
        </div>
        <div className="flex flex-col gap-2">
          <h3 className="text-[20px] leading-[24px] tracking-[0.4px]">
            {getEntryTitle(entry)}
          </h3>
          <p className="text-[16px] leading-[20px] tracking-[0.64px] text-white/60">
            {entry?.ru_summary || entry?.ru_explainer || 'Описание пока не добавлено'}
          </p>
        </div>
      </div>
    </Link>
  );
}

function CommentItem({ comment }) {
  const displayName = comment?.username || `Пользователь #${comment?.user_id || '—'}`;
  const initials = displayName.trim().slice(0, 1).toUpperCase();
  const avatarUrl = comment?.avatar_url;

  return (
    <div className="flex gap-4 rounded-[16px] border border-white/[0.06] bg-white/[0.03] p-4">
      <div className="h-14 w-14 shrink-0 overflow-hidden rounded-[12px] bg-white/10 flex items-center justify-center text-[20px] text-white/80">
        {avatarUrl ? (
          <img src={avatarUrl} alt="" className="h-full w-full object-cover" />
        ) : (
          <span>{initials}</span>
        )}
      </div>
      <div className="flex flex-1 flex-col gap-2">
        <div className="flex flex-wrap items-center justify-between gap-2 text-[16px] text-white">
          <span>{displayName}</span>
          <span className="text-[14px] text-white/50">{formatCommentDate(comment?.created_at)}</span>
        </div>
        <p className="text-[16px] leading-[22px] tracking-[0.64px] text-white/70 whitespace-pre-wrap">
          {comment?.body}
        </p>
      </div>
    </div>
  );
}

export default function KnowledgeArticle() {
  const navigate = useNavigate();
  const { id } = useParams();
  const [entry, setEntry] = useState(null);
  const [related, setRelated] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [comments, setComments] = useState([]);
  const [commentsLoading, setCommentsLoading] = useState(false);
  const [commentBody, setCommentBody] = useState('');
  const [commentStatus, setCommentStatus] = useState('idle');
  const [commentError, setCommentError] = useState('');

  useEffect(() => {
    let isMounted = true;

    const fetchEntry = async () => {
      try {
        setError('');
        const data = await knowledgeAPI.getEntry(id);
        if (isMounted) {
          setEntry(data);
        }
      } catch (err) {
        console.error('Не удалось загрузить статью', err);
        const detail = err?.response?.data?.detail;
        if (isMounted) {
          setError(typeof detail === 'string' ? detail : 'Не удалось загрузить статью');
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    if (id) {
      fetchEntry();
    } else {
      setLoading(false);
      setError('Не указан id статьи');
    }

    return () => {
      isMounted = false;
    };
  }, [id]);

  useEffect(() => {
    let isMounted = true;

    const fetchRelated = async () => {
      if (!entry) return;
      const tag = Array.isArray(entry.tags) ? entry.tags[0] : null;
      try {
        const data = await knowledgeAPI.getEntries({
          limit: 4,
          order: 'desc',
          tag: tag || undefined,
        });
        if (isMounted) {
          const filtered = (Array.isArray(data) ? data : []).filter(
            (item) => item.id !== entry.id
          );
          setRelated(filtered.slice(0, 2));
        }
      } catch (err) {
        console.error('Не удалось загрузить материалы по теме', err);
        if (isMounted) {
          setRelated([]);
        }
      }
    };

    fetchRelated();

    return () => {
      isMounted = false;
    };
  }, [entry]);

  useEffect(() => {
    let isMounted = true;

    const fetchComments = async () => {
      if (!entry) return;
      if (isMounted) {
        setCommentsLoading(true);
      }
      try {
        setCommentError('');
        const data = await knowledgeAPI.getComments(entry.id, { limit: 20, offset: 0 });
        if (isMounted) {
          setComments(Array.isArray(data) ? data : []);
        }
      } catch (err) {
        console.error('Не удалось загрузить комментарии', err);
        const detail = err?.response?.data?.detail;
        if (isMounted) {
          setCommentError(typeof detail === 'string' ? detail : 'Не удалось загрузить комментарии');
          setComments([]);
        }
      } finally {
        if (isMounted) {
          setCommentsLoading(false);
        }
      }
    };

    fetchComments();

    return () => {
      isMounted = false;
    };
  }, [entry]);

  const paragraphs = useMemo(() => {
    const text = entry?.ru_explainer || '';
    if (!text) return [];
    return text
      .split(/\n{2,}/)
      .map((chunk) => chunk.trim())
      .filter(Boolean);
  }, [entry]);

  if (loading) {
    return <div className="font-sans-figma text-white/60">Загрузка статьи...</div>;
  }

  if (error) {
    return <div className="font-sans-figma text-rose-300">{error}</div>;
  }

  if (!entry) {
    return null;
  }

  const tags = Array.isArray(entry.tags) ? entry.tags : [];
  const readTime = estimateReadTime(entry.ru_explainer || entry.ru_summary);
  const trimmedComment = commentBody.trim();
  const canSubmitComment = trimmedComment.length > 0 && trimmedComment.length <= 2000;

  const handleSubmitComment = async (event) => {
    event.preventDefault();
    if (!canSubmitComment || commentStatus === 'sending') return;
    try {
      setCommentStatus('sending');
      setCommentError('');
      const created = await knowledgeAPI.createComment(entry.id, { body: trimmedComment });
      setComments((prev) => [created, ...prev]);
      setCommentBody('');
      setCommentStatus('idle');
    } catch (err) {
      console.error('Не удалось отправить комментарий', err);
      const detail = err?.response?.data?.detail;
      setCommentError(typeof detail === 'string' ? detail : 'Не удалось отправить комментарий');
      setCommentStatus('idle');
    }
  };

  return (
    <div className="font-sans-figma text-white flex flex-col gap-10">
      <section className="relative overflow-hidden rounded-[20px] border border-white/[0.08] bg-white/[0.02]">
        <div
          className="relative min-h-[426px] px-6 py-6 sm:px-8 sm:py-8"
          style={{ backgroundImage: heroGradient }}
        >
          <img
            src={heroGlass}
            alt=""
            aria-hidden="true"
            className="pointer-events-none absolute right-[-140px] top-[-220px] h-[847px] w-[1243px] opacity-90"
          />

          <div className="relative z-10 flex max-w-[620px] flex-col gap-6">
            <button
              onClick={() => navigate(-1)}
              className="inline-flex w-fit items-center gap-2 rounded-[10px] border border-white/10 bg-white/10 px-4 py-2 text-[14px] text-white/80 transition hover:border-[#9B6BFF]/60 hover:text-white"
            >
              <img src={arrowLeftIcon} alt="" className="h-5 w-5" />
              Назад
            </button>

            <div className="flex flex-wrap items-center gap-3 text-[14px] text-white/70">
              <span className="inline-flex items-center gap-1">
                <img src={eyeIcon} alt="" className="h-3.5 w-3.5" />
                {entry?.views ?? 0}
              </span>
              {tags.slice(0, 2).map((tag) => (
                <span
                  key={tag}
                  className="rounded-[10px] border border-[#8E51FF]/30 bg-[#8E51FF]/10 px-[13px] py-[9px] text-[16px] tracking-[0.64px] text-[#A684FF]"
                >
                  {tag}
                </span>
              ))}
              <span className="text-white/60">{readTime} мин</span>
            </div>

            <div className="flex flex-col gap-4">
              <h1 className="text-[29px] leading-[36px] tracking-[0.58px] font-medium">
                {getEntryTitle(entry)}
              </h1>
              <p className="text-[16px] leading-[20px] tracking-[0.64px] text-white/70">
                {entry?.ru_summary || entry?.ru_explainer || 'Описание пока не добавлено'}
              </p>
            </div>

            <span className="inline-flex w-fit rounded-[10px] border border-white/10 bg-white/10 px-4 py-1.5 text-[14px] text-white/70">
              {formatDate(entry?.created_at)}
            </span>
          </div>
        </div>
      </section>

      <section className="flex flex-col gap-8 lg:flex-row">
        <div className="flex gap-3 lg:w-[142px] lg:flex-col">
          {tags.slice(0, 4).map((tag) => (
            <span
              key={tag}
              className="rounded-[12px] border border-white/10 bg-white/[0.05] px-4 py-3 text-[14px] text-white/70"
            >
              {tag}
            </span>
          ))}
        </div>

        <article className="flex-1 max-w-[900px]">
          {paragraphs.length === 0 ? (
            <p className="text-white/60">Контент статьи пока не добавлен.</p>
          ) : (
            <div className="flex flex-col gap-4 text-[16px] leading-[24px] tracking-[0.64px] text-white/70 whitespace-pre-wrap">
              {paragraphs.map((paragraph, index) => (
                <p key={`${paragraph.slice(0, 12)}-${index}`}>{paragraph}</p>
              ))}
            </div>
          )}
        </article>
      </section>

      <section className="flex max-w-[900px] flex-col gap-6">
        <h2 className="text-[29px] leading-[36px] tracking-[0.58px] font-medium">Комментарии</h2>
        <form onSubmit={handleSubmitComment} className="rounded-[16px] border border-white/[0.06] bg-white/[0.03] p-4">
          <textarea
            rows={4}
            maxLength={2000}
            value={commentBody}
            onChange={(event) => setCommentBody(event.target.value)}
            placeholder="Комментарий, если есть"
            className="w-full resize-none rounded-[12px] border border-white/10 bg-[#111118] px-4 py-3 text-[16px] text-white/80 placeholder:text-white/40 focus:outline-none focus:border-[#9B6BFF]/70"
          />
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <span className="text-[13px] text-white/40">
              {commentBody.length}/2000
            </span>
            <button
              type="submit"
              disabled={!canSubmitComment || commentStatus === 'sending'}
              className={`rounded-[10px] px-6 py-3 text-[16px] ${
                canSubmitComment && commentStatus !== 'sending'
                  ? 'bg-[#9B6BFF] text-white'
                  : 'bg-white/10 text-white/40'
              }`}
            >
              {commentStatus === 'sending' ? 'Отправка...' : 'Опубликовать'}
            </button>
          </div>
          {commentError && (
            <div className="mt-3 text-[14px] text-rose-300">{commentError}</div>
          )}
        </form>
        {commentsLoading && (
          <div className="text-white/50 text-[16px]">Загрузка комментариев...</div>
        )}
        {!commentsLoading && comments.length === 0 && !commentError && (
          <div className="text-white/50 text-[16px]">Пока нет комментариев</div>
        )}
        {!commentsLoading && comments.length > 0 && (
          <div className="flex flex-col gap-4">
            {comments.map((comment) => (
              <CommentItem key={comment.id} comment={comment} />
            ))}
          </div>
        )}
      </section>

      <section className="flex max-w-[900px] flex-col gap-6">
        <div className="flex items-center justify-between">
          <h2 className="text-[29px] leading-[36px] tracking-[0.58px] font-medium">Материалы по теме</h2>
          <Link to="/knowledge" className="text-[14px] text-white/60 hover:text-[#9B6BFF]">
            Смотреть все
          </Link>
        </div>
        {related.length === 0 ? (
          <div className="text-white/60">Пока нет материалов</div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {related.map((item) => (
              <RelatedCard key={item.id} entry={item} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
