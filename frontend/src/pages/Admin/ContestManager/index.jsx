import React, { useState, useEffect, useCallback } from 'react';
import ContestGrid from './ContestGrid';
import ActivityFeed from './ActivityFeed';
import ContestCreateModal from '../../../components/ContestCreateModal';
import { adminAPI } from '../../../services/api';

export default function ContestManager() {
  const [contests, setContests] = useState([]);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [pageSize, setPageSize] = useState(6);  // Configurable

  // Load contests
  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        const [contestsRes] = await Promise.all([
          adminAPI.listContests(),
        ]);
        setContests(Array.isArray(contestsRes) ? contestsRes : []);
        setError(null);
      } catch (err) {
        console.error('Failed to load data:', err);
        setError(err.response?.data?.detail || 'Failed to load data');
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [refreshKey]);

  // Callbacks
  const handleCreateSuccess = useCallback(() => {
    setIsCreateModalOpen(false);
    setRefreshKey(prev => prev + 1);  // Trigger reload
  }, []);

  const handleEditSuccess = useCallback(() => {
    setRefreshKey(prev => prev + 1);
  }, []);

  const handleDeleteSuccess = useCallback(() => {
    setRefreshKey(prev => prev + 1);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-lg text-gray-400">Загрузка...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-900 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-3xl font-bold text-white">Управление чемпионатами</h1>
          <button
            onClick={() => setIsCreateModalOpen(true)}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition"
          >
            + Создать
          </button>
        </div>

        {/* Error message */}
        {error && (
          <div className="mb-6 p-4 bg-red-900/30 border border-red-700 rounded-lg text-red-200">
            {error}
          </div>
        )}

        {/* Main layout: grid + feed side by side (responsive) */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Contest grid (left, 2/3) */}
          <div className="lg:col-span-2">
            <ContestGrid
              contests={contests}
              pageSize={pageSize}
              onPageSizeChange={setPageSize}
              onEditSuccess={handleEditSuccess}
              onDeleteSuccess={handleDeleteSuccess}
            />
          </div>

          {/* Activity feed (right, 1/3) */}
          <div>
            <ActivityFeed
              refreshKey={refreshKey}
            />
          </div>
        </div>
      </div>

      {/* Create Contest Modal */}
      {isCreateModalOpen && (
        <ContestCreateModal
          isOpen={isCreateModalOpen}
          onClose={() => setIsCreateModalOpen(false)}
          onSuccess={handleCreateSuccess}
        />
      )}
    </div>
  );
}
