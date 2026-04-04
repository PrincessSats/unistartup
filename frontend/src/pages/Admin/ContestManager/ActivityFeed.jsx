import React, { useState, useEffect, useCallback } from 'react';
import { adminAPI } from '../../../services/api';

const eventTypeColors = {
  contest_created: 'text-green-400',
  contest_updated: 'text-blue-400',
  contest_deleted: 'text-red-400',
  contest_ended: 'text-yellow-400',
  task_added: 'text-cyan-400',
  task_removed: 'text-red-400',
  submission_received: 'text-slate-400',
  submission_correct: 'text-green-400',
  submission_incorrect: 'text-red-400',
  participant_joined: 'text-purple-400',
  participant_left: 'text-slate-400',
  chat_message: 'text-indigo-400',
};

const eventTypeIcons = {
  contest_created: '✨',
  contest_updated: '✏️',
  contest_deleted: '🗑️',
  contest_ended: '⏹️',
  task_added: '➕',
  task_removed: '➖',
  submission_received: '📤',
  submission_correct: '✅',
  submission_incorrect: '❌',
  participant_joined: '👤',
  participant_left: '👋',
  chat_message: '💬',
};

export default function ActivityFeed({ refreshKey }) {
  const [logs, setLogs] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [loading, setLoading] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [eventTypeFilter] = useState([]);
  const [sourceFilter, setSourceFilter] = useState('all');
  const [expandedEventId, setExpandedEventId] = useState(null);

  // Load activity logs
  const loadLogs = useCallback(async (pageNum = 1) => {
    try {
      setLoading(true);
      const res = await adminAPI.getActivityLog({
        page: pageNum,
        page_size: pageSize,
        event_type: eventTypeFilter.length > 0 ? eventTypeFilter[0] : undefined,
        source: sourceFilter !== 'all' ? sourceFilter : undefined,
        search_text: searchText || undefined,
      });
      setLogs(res.data?.items || []);
      setTotal(res.data?.total || 0);
      setPage(pageNum);
    } catch (err) {
      console.error('Failed to load activity logs:', err);
    } finally {
      setLoading(false);
    }
  }, [pageSize, eventTypeFilter, sourceFilter, searchText]);

  // Reload when filters change or refreshKey updates
  useEffect(() => {
    loadLogs(1);
  }, [eventTypeFilter, sourceFilter, searchText, refreshKey, loadLogs]);

  const handleSearch = (e) => {
    setSearchText(e.target.value);
  };

  const handleNextPage = () => {
    if (page * pageSize < total) {
      loadLogs(page + 1);
    }
  };

  const handlePrevPage = () => {
    if (page > 1) {
      loadLogs(page - 1);
    }
  };

  const formatTime = (dateStr) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = Math.floor((now - date) / 1000);

    if (diff < 60) return `${diff}с назад`;
    if (diff < 3600) return `${Math.floor(diff / 60)}м назад`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}ч назад`;
    return date.toLocaleDateString('ru-RU');
  };

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg overflow-hidden flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-slate-700">
        <h2 className="text-lg font-semibold text-white">Лента активности</h2>
      </div>

      {/* Search box */}
      <div className="px-4 pt-4 pb-2">
        <input
          type="text"
          placeholder="Поиск..."
          value={searchText}
          onChange={handleSearch}
          className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 text-sm"
        />
      </div>

      {/* Filters */}
      <div className="px-4 py-2 border-t border-slate-700">
        <div className="text-xs text-slate-400 mb-2">Источник:</div>
        <div className="flex gap-1">
          {['all', 'admin_action', 'system_event', 'participant_action'].map(src => (
            <button
              key={src}
              onClick={() => setSourceFilter(src)}
              className={`px-2 py-1 text-xs rounded transition ${
                sourceFilter === src
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
              }`}
            >
              {src === 'all' ? 'Все' : src.replace(/_/g, ' ')}
            </button>
          ))}
        </div>
      </div>

      {/* Event list */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="p-4 text-center text-slate-400 text-sm">Загрузка...</div>
        ) : logs.length === 0 ? (
          <div className="p-4 text-center text-slate-400 text-sm">Нет событий</div>
        ) : (
          <div className="divide-y divide-slate-700">
            {logs.map(log => (
              <div
                key={log.id}
                onClick={() => setExpandedEventId(expandedEventId === log.id ? null : log.id)}
                className="p-3 hover:bg-slate-700/50 cursor-pointer transition text-sm border-l-2 border-slate-700"
              >
                <div className="flex items-start gap-2">
                  <span className="text-lg leading-none">
                    {eventTypeIcons[log.event_type] || '📌'}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className={`font-medium text-sm ${eventTypeColors[log.event_type] || 'text-slate-300'}`}>
                      {log.action}
                    </p>
                    <p className="text-xs text-slate-500 mt-1">{formatTime(log.created_at)}</p>
                  </div>
                </div>

                {/* Expanded details */}
                {expandedEventId === log.id && log.details && (
                  <div className="mt-3 p-2 bg-slate-900 rounded text-xs text-slate-300 font-mono overflow-x-auto">
                    <pre>{JSON.stringify(log.details, null, 2)}</pre>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Pagination */}
      {logs.length > 0 && (
        <div className="p-3 border-t border-slate-700 flex items-center justify-between text-xs text-slate-400">
          <span>{logs.length} из {total}</span>
          <div className="flex gap-2">
            <button
              onClick={handlePrevPage}
              disabled={page === 1}
              className="px-2 py-1 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 rounded transition"
            >
              ← Пред
            </button>
            <span className="px-2 py-1">{page}</span>
            <button
              onClick={handleNextPage}
              disabled={page * pageSize >= total}
              className="px-2 py-1 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 rounded transition"
            >
              След →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
