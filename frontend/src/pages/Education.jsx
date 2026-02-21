import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import AppIcon from '../components/AppIcon';
import { educationAPI } from '../services/api';
import { getEducationCardVisual } from '../utils/educationVisuals';

const difficultyOptions = [
  { value: '', label: 'Сложность' },
  { value: 'easy', label: 'Легко' },
  { value: 'medium', label: 'Средне' },
  { value: 'hard', label: 'Сложно' },
];

const statusOptions = [
  { value: '', label: 'Статус' },
  { value: 'not_started', label: 'Не начато' },
  { value: 'in_progress', label: 'В процессе' },
  { value: 'solved', label: 'Решено' },
];

const difficultyBadgeClasses = {
  Легко: 'border-[#3FD18A]/30 bg-[#3FD18A]/10 text-[#3FD18A]',
  Средне: 'border-[#F2C94C]/30 bg-[#F2C94C]/10 text-[#F2C94C]',
  Сложно: 'border-[#FF5A6E]/30 bg-[#FF5A6E]/10 text-[#FF5A6E]',
};

function EducationCard({ task }) {
  const visual = getEducationCardVisual(task);
  const difficultyClass = difficultyBadgeClasses[task?.difficulty_label] || difficultyBadgeClasses['Средне'];
  const isSolved = task?.my_status === 'solved';

  return (
    <Link
      to={`/education/${task.id}`}
      className="group rounded-[12px] border border-white/[0.06] bg-white/[0.03] p-6 transition hover:border-[#9B6BFF]/60"
    >
      <div className="relative h-[173px] overflow-hidden rounded-[10px] border border-white/[0.06] bg-black/20">
        <img
          src={visual}
          alt=""
          loading="lazy"
          className="h-full w-full object-cover transition duration-300 group-hover:scale-[1.02]"
        />
        {isSolved && (
          <span className="absolute right-3 top-3 inline-flex items-center gap-1.5 rounded-[8px] border border-[#3FD18A]/45 bg-[#3FD18A]/20 px-2.5 py-1 text-[12px] text-[#3FD18A]">
            <AppIcon name="check-circle" className="h-3.5 w-3.5" />
            Решено
          </span>
        )}
      </div>

      <div className="mt-6 flex min-h-[190px] flex-col justify-between">
        <div>
          <h3 className="text-[28px] leading-[1.15] tracking-[0.01em] text-white">
            {task.title}
          </h3>
          <p className="mt-4 line-clamp-2 text-[16px] leading-[20px] tracking-[0.04em] text-white/60">
            {task.summary || 'Описание задачи пока не добавлено'}
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <span className="rounded-[10px] border border-white/[0.14] bg-white/[0.05] px-3 py-1.5 text-[12px] text-white/75">
              {task.category}
            </span>
            <span className={`rounded-[10px] border px-3 py-1.5 text-[12px] ${difficultyClass}`}>
              {task.difficulty_label}
            </span>
            {isSolved && (
              <span className="inline-flex items-center gap-1.5 rounded-[10px] border border-[#3FD18A]/45 bg-[#3FD18A]/20 px-3 py-1.5 text-[12px] text-[#3FD18A]">
                <AppIcon name="check-circle" className="h-3.5 w-3.5" />
                Завершено
              </span>
            )}
          </div>
        </div>

        <div className="mt-6 flex items-center justify-between text-[16px] leading-[20px] tracking-[0.04em] text-white/65">
          <span>{task.passed_users_count} прошли</span>
          <span className="inline-flex items-center gap-2 font-mono-figma text-white">
            <AppIcon name="star" className="h-4 w-4 text-white/80" />
            {task.points}
          </span>
        </div>
      </div>
    </Link>
  );
}

export default function Education() {
  const [difficultyFilter, setDifficultyFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [tasks, setTasks] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let isMounted = true;

    const fetchTasks = async () => {
      if (isMounted) {
        setLoading(true);
      }
      try {
        setError('');
        const response = await educationAPI.getPracticeTasks({
          difficulty: difficultyFilter || undefined,
          category: categoryFilter || undefined,
          status: statusFilter || undefined,
          limit: 100,
          offset: 0,
        });
        if (!isMounted) return;
        setTasks(Array.isArray(response?.items) ? response.items : []);
        setCategories(Array.isArray(response?.categories) ? response.categories : []);
      } catch (err) {
        console.error('Не удалось загрузить практические задачи', err);
        if (!isMounted) return;
        const detail = err?.response?.data?.detail;
        setError(typeof detail === 'string' ? detail : 'Не удалось загрузить задачи');
        setTasks([]);
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    fetchTasks();
    return () => {
      isMounted = false;
    };
  }, [difficultyFilter, categoryFilter, statusFilter]);

  return (
    <div className="font-sans-figma text-white">
      <div className="flex flex-col gap-5">
        <div className="flex items-center justify-between gap-6">
          <h1 className="text-[39px] leading-[44px] tracking-[0.02em]">Обучение</h1>
          <div className="flex items-center gap-2 rounded-[10px] border border-white/[0.06] bg-white/[0.02] p-1">
            <button
              type="button"
              disabled
              className="rounded-[8px] px-4 py-2 text-[14px] text-white/45"
            >
              Теория
            </button>
            <button
              type="button"
              className="rounded-[8px] bg-[#9B6BFF]/20 px-4 py-2 text-[14px] text-[#C9AEFF]"
            >
              Практика
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <div className="relative">
            <select
              value={difficultyFilter}
              onChange={(event) => setDifficultyFilter(event.target.value)}
              className="h-14 w-full appearance-none rounded-[10px] border border-white/[0.09] bg-white/[0.03] px-4 pr-10 text-[16px] text-white/75 outline-none transition focus:border-[#9B6BFF]/70"
            >
              {difficultyOptions.map((option) => (
                <option key={option.value || 'all'} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <span className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-white/45">▾</span>
          </div>

          <div className="relative">
            <select
              value={categoryFilter}
              onChange={(event) => setCategoryFilter(event.target.value)}
              className="h-14 w-full appearance-none rounded-[10px] border border-white/[0.09] bg-white/[0.03] px-4 pr-10 text-[16px] text-white/75 outline-none transition focus:border-[#9B6BFF]/70"
            >
              <option value="">Категория</option>
              {categories.map((category) => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </select>
            <span className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-white/45">▾</span>
          </div>

          <div className="relative">
            <select
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value)}
              className="h-14 w-full appearance-none rounded-[10px] border border-white/[0.09] bg-white/[0.03] px-4 pr-10 text-[16px] text-white/75 outline-none transition focus:border-[#9B6BFF]/70"
            >
              {statusOptions.map((option) => (
                <option key={option.value || 'all'} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <span className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-white/45">▾</span>
          </div>
        </div>
      </div>

      <div className="mt-6">
        {loading && <p className="text-white/60">Загрузка задач...</p>}
        {!loading && error && <p className="text-rose-300">{error}</p>}
        {!loading && !error && tasks.length === 0 && <p className="text-white/60">Подходящих задач пока нет.</p>}
      </div>

      {!loading && !error && tasks.length > 0 && (
        <div className="mt-6 grid grid-cols-1 gap-4 xl:grid-cols-2 2xl:grid-cols-4">
          {tasks.map((task) => (
            <EducationCard key={task.id} task={task} />
          ))}
        </div>
      )}
    </div>
  );
}
