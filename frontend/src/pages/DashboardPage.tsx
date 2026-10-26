import React, { useState, useEffect } from 'react';
import { 
  Users, 
  Clock, 
  AlertTriangle, 
  Utensils, 
  CheckCircle2, 
  Layers, 
  X, 
  Search, 
  Download, 
  RotateCcw,
  BellRing,
  Map,
  LayoutGrid,
  Camera,
  Plus,
  Minus,
  Sparkles
} from 'lucide-react';
import { 
  Table, 
  Alert, 
  TimelineItem, 
  StaffUser 
} from '../types';
import { 
  acknowledgeAlert, 
  resolveAlert, 
  fetchSessionTimeline, 
  confirmAttendance, 
  confirmFoodDelivery, 
  cleanTable,
  overrideTableState,
  getExportCsvUrl
} from '../services/api';
import { FloorPlanMap } from '../components/FloorPlanMap';
import { soundService } from '../services/sound';
import { 
  getActiveTrackingFootage, 
  getStoredTrackingFootages, 
  setActiveTrackingFootage 
} from '../services/trackingFootages';


interface DashboardPageProps {
  tables: Table[];
  alerts: Alert[];
  currentActor: StaffUser;
  onRefresh: () => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({
  tables,
  alerts,
  currentActor,
  onRefresh,
}) => {
  // View mode: Floor Plan Map or Grid Cards
  const [viewMode, setViewMode] = useState<'map' | 'grid'>('map');

  // Filter & Search states
  const [searchQuery, setSearchQuery] = useState('');
  const [filterSection, setFilterSection] = useState('ALL');
  const [filterStatus, setFilterStatus] = useState('ALL');

  // Selected table for side detail drawer
  const [selectedTable, setSelectedTable] = useState<Table | null>(tables[0] || null);
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [isLoadingTimeline, setIsLoadingTimeline] = useState(false);

  // Operational action states
  const [actionFeedback, setActionFeedback] = useState<{ success: boolean; message: string } | null>(null);
  const [isSubmittingAction, setIsSubmittingAction] = useState(false);
  const [deliveryCourse, setDeliveryCourse] = useState('Mains');
  const [deliveryBatch, setDeliveryBatch] = useState(1);
  const [guestCountInput, setGuestCountInput] = useState<number>(2);

  // Sync selectedTable when tables list updates
  useEffect(() => {
    if (selectedTable) {
      const updated = tables.find(t => t.id === selectedTable.id);
      if (updated) {
        setSelectedTable(updated);
      }
    } else if (tables.length > 0) {
      setSelectedTable(tables[0]);
    }
  }, [tables]);

  // Load timeline whenever selectedTable changes
  useEffect(() => {
    let isMounted = true;
    if (selectedTable?.currentSessionId) {
      setIsLoadingTimeline(true);
      fetchSessionTimeline(selectedTable.currentSessionId).then((items) => {
        if (isMounted) {
          setTimeline(items);
          setIsLoadingTimeline(false);
        }
      });
    } else {
      setTimeline([]);
    }
    return () => { isMounted = false; };
  }, [selectedTable?.id, selectedTable?.currentSessionId]);

  // Compute live KPIs
  const totalTables = tables.length;
  const occupiedCount = tables.filter(t => t.status === 'OCCUPIED' || t.status === 'ATTENDED' || t.status === 'FOOD_DELIVERED').length;
  const availableCount = tables.filter(t => t.status === 'VACANT').length;
  const cleaningCount = tables.filter(t => t.status === 'CLEANING_REQUIRED').length;
  const overdueCount = tables.filter(t => t.status === 'OCCUPIED' && ((t.timeSinceLastAttendanceSec || 0) > 180 || t.hasActiveAlert)).length;
  const totalGuests = tables.reduce((acc, t) => acc + (t.customerCount || 0), 0);
  const occupancyPercentage = totalTables > 0 ? Math.round((occupiedCount / totalTables) * 100) : 0;

  // Filter tables
  const filteredTables = tables.filter((tbl) => {
    const matchesSearch = tbl.code.toLowerCase().includes(searchQuery.toLowerCase()) || 
                          tbl.section.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesSection = filterSection === 'ALL' || tbl.section === filterSection;
    const matchesStatus = filterStatus === 'ALL' || tbl.status === filterStatus;
    return matchesSearch && matchesSection && matchesStatus;
  });

  const uniqueSections = Array.from(new Set(tables.map(t => t.section).filter(Boolean)));

  // Handlers for Alert actions
  const handleAcknowledgeAlert = async (alertId: string) => {
    await acknowledgeAlert(alertId);
    onRefresh();
  };

  const handleResolveAlert = async (alertId: string) => {
    await resolveAlert(alertId);
    onRefresh();
  };

  // Paging assigned waiter
  const handlePageWaiter = () => {
    soundService.playChime();
    setActionFeedback({
      success: true,
      message: `Chime sent to ${selectedTable?.assignedWaiter || 'Waitstaff'} for Table ${selectedTable?.code}.`,
    });
    setTimeout(() => setActionFeedback(null), 4000);
  };

  // Guest headcount adjustment
  const handleAdjustGuestCount = async (delta: number) => {
    if (!selectedTable) return;
    const newCount = Math.max(1, (selectedTable.customerCount || 2) + delta);
    setIsSubmittingAction(true);
    const res = await overrideTableState(selectedTable.id, selectedTable.status, newCount, `Guest count updated to ${newCount}`);
    setIsSubmittingAction(false);
    if (res.success) {
      setSelectedTable({ ...selectedTable, customerCount: newCount });
      onRefresh();
    }
  };

  // Operational Actions
  const handleSeatWalkIn = async () => {
    if (!selectedTable) return;
    setIsSubmittingAction(true);
    setActionFeedback(null);
    const res = await overrideTableState(selectedTable.id, 'OCCUPIED', guestCountInput, `Walk-in party seated (${guestCountInput} guests)`);
    setIsSubmittingAction(false);
    soundService.playChime();
    setActionFeedback(res);
    if (res.success) {
      onRefresh();
      setSelectedTable({ ...selectedTable, status: 'OCCUPIED', customerCount: guestCountInput });
    }
  };

  const handleConfirmAttendance = async () => {
    if (!selectedTable) return;
    setIsSubmittingAction(true);
    setActionFeedback(null);
    const res = await confirmAttendance(selectedTable.id, selectedTable.currentSessionId);
    setIsSubmittingAction(false);
    soundService.playChime();
    setActionFeedback(res);
    if (res.success) {
      onRefresh();
      if (selectedTable.currentSessionId) {
        fetchSessionTimeline(selectedTable.currentSessionId).then(setTimeline);
      }
    }
  };

  const handleConfirmFoodDelivery = async () => {
    if (!selectedTable) return;
    setIsSubmittingAction(true);
    setActionFeedback(null);
    const res = await confirmFoodDelivery(selectedTable.id, selectedTable.currentSessionId, deliveryCourse, deliveryBatch);
    setIsSubmittingAction(false);
    soundService.playChime();
    setActionFeedback(res);
    if (res.success) {
      onRefresh();
      if (selectedTable.currentSessionId) {
        fetchSessionTimeline(selectedTable.currentSessionId).then(setTimeline);
      }
    }
  };

  const handleDepartParty = async () => {
    if (!selectedTable) return;
    setIsSubmittingAction(true);
    setActionFeedback(null);
    const res = await overrideTableState(selectedTable.id, 'CLEANING_REQUIRED', 0, 'Party departed; table ready for bussing');
    setIsSubmittingAction(false);
    setActionFeedback(res);
    if (res.success) {
      onRefresh();
      setSelectedTable({ ...selectedTable, status: 'CLEANING_REQUIRED', customerCount: 0 });
    }
  };

  const handleSanitizeAndReset = async () => {
    if (!selectedTable) return;
    setIsSubmittingAction(true);
    setActionFeedback(null);
    const res = await cleanTable(selectedTable.id);
    setIsSubmittingAction(false);
    setActionFeedback(res);
    if (res.success) {
      onRefresh();
      setSelectedTable({ ...selectedTable, status: 'VACANT', customerCount: 0 });
    }
  };

  return (
    <div className="page-wrapper">
      {/* 1. Page Title & View Switcher Bar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '16px',
        marginBottom: '20px',
      }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '-0.02em', margin: 0 }}>
            Floor Operations & Table Service
          </h1>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', margin: '4px 0 0 0' }}>
            Live table status, guest turnover velocity, service timers, and staff intervention controls.
          </p>
        </div>

        {/* View Switcher & Export */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {/* View Mode Toggle: Floor Plan Map vs Grid */}
          <div style={{
            display: 'flex',
            background: '#ffffff',
            border: '1px solid var(--border-medium)',
            borderRadius: 'var(--radius-md)',
            padding: '3px',
            boxShadow: 'var(--shadow-sm)',
          }}>
            <button
              onClick={() => setViewMode('map')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 14px',
                borderRadius: 'var(--radius-sm)',
                fontSize: '0.8rem',
                fontWeight: 600,
                background: viewMode === 'map' ? 'var(--accent-primary)' : 'transparent',
                color: viewMode === 'map' ? '#ffffff' : 'var(--text-muted)',
              }}
            >
              <Map size={14} />
              <span>Floor Plan</span>
            </button>

            <button
              onClick={() => setViewMode('grid')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 14px',
                borderRadius: 'var(--radius-sm)',
                fontSize: '0.8rem',
                fontWeight: 600,
                background: viewMode === 'grid' ? 'var(--accent-primary)' : 'transparent',
                color: viewMode === 'grid' ? '#ffffff' : 'var(--text-muted)',
              }}
            >
              <LayoutGrid size={14} />
              <span>Table Cards</span>
            </button>
          </div>

          {/* Quick Export CSV */}
          <a
            href={getExportCsvUrl('sessions', { anonymize: true })}
            target="_blank"
            rel="noreferrer"
            download="restaurant_operations_export.csv"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '7px 14px',
              background: '#ffffff',
              border: '1px solid var(--border-medium)',
              borderRadius: 'var(--radius-md)',
              fontSize: '0.8rem',
              fontWeight: 600,
              color: 'var(--text-main)',
              textDecoration: 'none',
              boxShadow: 'var(--shadow-sm)',
            }}
          >
            <Download size={14} color="var(--accent-primary)" />
            <span>Export CSV</span>
          </a>
        </div>
      </div>

      {/* 2. Active AI Tracking Footage Banner & Channel Quick Switcher */}
      {(() => {
        const activeF = getActiveTrackingFootage();
        const storedF = getStoredTrackingFootages();
        const totalGuests = tables.reduce((acc, t) => acc + (t.customerCount || 0), 0);

        return (
          <div style={{
            background: 'linear-gradient(to right, #eff6ff, #f8fafc)',
            border: '1px solid #bfdbfe',
            borderRadius: 'var(--radius-lg)',
            padding: '12px 18px',
            marginBottom: '20px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '12px',
            boxShadow: 'var(--shadow-sm)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <div className="live-indicator" />
                <span style={{ fontSize: '0.76rem', fontWeight: 800, color: 'var(--accent-primary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  Active Tracking Channel:
                </span>
                <span style={{ fontSize: '0.88rem', fontWeight: 800, color: 'var(--text-main)' }}>
                  {activeF.name}
                </span>
                <span className="badge badge-occupied" style={{ fontSize: '0.68rem' }}>
                  {activeF.section}
                </span>
              </div>

              <span style={{ color: 'var(--border-medium)' }}>|</span>

              <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                Monitoring <strong>{tables.length} tables</strong> ({tables.map(t => t.code).join(', ')}) with <strong>{totalGuests} seated guests</strong> ({activeF.modelName})
              </div>
            </div>

            {/* Quick Switcher Pills */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', overflowX: 'auto' }}>
              <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)', fontWeight: 600 }}>Switch Footage:</span>
              {storedF.map((f) => {
                const isSelected = f.id === activeF.id;
                return (
                  <button
                    key={f.id}
                    onClick={() => {
                      setActiveTrackingFootage(f.id);
                      onRefresh();
                    }}
                    style={{
                      padding: '5px 12px',
                      borderRadius: 'var(--radius-sm)',
                      fontSize: '0.74rem',
                      fontWeight: isSelected ? 800 : 600,
                      background: isSelected ? 'var(--accent-primary)' : '#ffffff',
                      color: isSelected ? '#ffffff' : 'var(--text-main)',
                      border: isSelected ? 'none' : '1px solid var(--border-medium)',
                      cursor: 'pointer',
                      boxShadow: 'var(--shadow-sm)',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {f.name.split('(')[0].trim()}
                  </button>
                );
              })}
            </div>
          </div>
        );
      })()}


      {/* 2. Restaurant Operational KPI Summary Cards */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
        gap: '14px',
        marginBottom: '22px',
      }}>
        {/* Total Tables & Capacity */}
        <div className="white-card" style={{ padding: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', fontWeight: 700, textTransform: 'uppercase' }}>Total Tables</span>
            <Layers size={16} color="var(--text-muted)" />
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--text-main)' }}>
            {totalTables}
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '2px' }}>
            Across {uniqueSections.length} sections
          </div>
        </div>

        {/* Occupied / Seated */}
        <div className="white-card" style={{ padding: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', fontWeight: 700, textTransform: 'uppercase' }}>Occupied / Seated</span>
            <Users size={16} color="var(--status-occupied)" />
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
            <span style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--status-occupied)' }}>
              {occupiedCount}
            </span>
            <span style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)' }}>
              ({occupancyPercentage}% cap)
            </span>
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '2px' }}>
            {totalGuests} total guests seated
          </div>
        </div>

        {/* Available / Ready Tables */}
        <div className="white-card" style={{ padding: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', fontWeight: 700, textTransform: 'uppercase' }}>Ready for Seating</span>
            <CheckCircle2 size={16} color="var(--status-vacant)" />
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--status-vacant)' }}>
            {availableCount}
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '2px' }}>
            Clean & ready for walk-ins
          </div>
        </div>

        {/* Overdue Waiter Greeting */}
        <div className="white-card" style={{ padding: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', fontWeight: 700, textTransform: 'uppercase' }}>Overdue Greeting</span>
            <Clock size={16} color={overdueCount > 0 ? 'var(--status-warning)' : 'var(--text-dim)'} />
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 800, color: overdueCount > 0 ? 'var(--status-warning)' : 'var(--text-main)' }}>
            {overdueCount}
          </div>
          <div style={{ fontSize: '0.72rem', color: overdueCount > 0 ? 'var(--status-warning)' : 'var(--text-muted)', marginTop: '2px' }}>
            {overdueCount > 0 ? 'Seated > 3m without waiter' : 'All tables greeted in time'}
          </div>
        </div>

        {/* Needs Cleaning / Bussing */}
        <div className="white-card" style={{ padding: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', fontWeight: 700, textTransform: 'uppercase' }}>Bussing Required</span>
            <RotateCcw size={16} color="var(--status-cleaning)" />
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 800, color: 'var(--status-cleaning)' }}>
            {cleaningCount}
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '2px' }}>
            Parties departed; sanitize
          </div>
        </div>

        {/* Active Operational Alerts */}
        <div className="white-card" style={{ padding: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-dim)', fontWeight: 700, textTransform: 'uppercase' }}>Active Alerts</span>
            <AlertTriangle size={16} color={alerts.length > 0 ? 'var(--status-critical)' : 'var(--text-dim)'} />
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 800, color: alerts.length > 0 ? 'var(--status-critical)' : 'var(--text-main)' }}>
            {alerts.length}
          </div>
          <div style={{ fontSize: '0.72rem', color: alerts.length > 0 ? 'var(--status-critical)' : 'var(--text-muted)', marginTop: '2px' }}>
            {alerts.length > 0 ? 'Urgent attention needed' : 'Floor running smoothly'}
          </div>
        </div>
      </div>

      {/* 3. Main Workspace: Left = Floor Plan / Grid + Alert Queue; Right = Table Details Drawer */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'minmax(0, 1fr) 380px',
        gap: '24px',
        alignItems: 'start',
      }}>
        {/* Left Side: Visual Floor Plan or Grid Cards + Alerts */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {viewMode === 'map' ? (
            <FloorPlanMap
              tables={tables}
              selectedTableId={selectedTable?.id || null}
              onSelectTable={(tbl) => setSelectedTable(tbl)}
            />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {/* Filter Bar for Grid View */}
              <div className="white-card" style={{
                padding: '14px 18px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '12px',
              }}>
                {/* Search */}
                <div style={{ position: 'relative', minWidth: '220px' }}>
                  <Search size={14} color="var(--text-dim)" style={{ position: 'absolute', left: '10px', top: '10px' }} />
                  <input
                    type="text"
                    placeholder="Search table or section..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    style={{ paddingLeft: '32px', width: '100%' }}
                  />
                </div>

                {/* Filters */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                  <select
                    value={filterSection}
                    onChange={(e) => setFilterSection(e.target.value)}
                    style={{ fontSize: '0.8rem' }}
                  >
                    <option value="ALL">All Sections</option>
                    {uniqueSections.map((sec) => (
                      <option key={sec} value={sec}>{sec}</option>
                    ))}
                  </select>

                  <select
                    value={filterStatus}
                    onChange={(e) => setFilterStatus(e.target.value)}
                    style={{ fontSize: '0.8rem' }}
                  >
                    <option value="ALL">All States</option>
                    <option value="VACANT">Ready / Vacant</option>
                    <option value="OCCUPIED">Seated / Occupied</option>
                    <option value="ATTENDED">Attended / Ordered</option>
                    <option value="FOOD_DELIVERED">Food Delivered</option>
                    <option value="CLEANING_REQUIRED">Needs Bussing</option>
                  </select>

                  {(filterSection !== 'ALL' || filterStatus !== 'ALL' || searchQuery !== '') && (
                    <button
                      onClick={() => {
                        setFilterSection('ALL');
                        setFilterStatus('ALL');
                        setSearchQuery('');
                      }}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                        fontSize: '0.75rem',
                        color: 'var(--text-muted)',
                        padding: '5px 10px',
                        borderRadius: 'var(--radius-sm)',
                        background: '#f1f5f9',
                      }}
                    >
                      <X size={12} />
                      <span>Reset</span>
                    </button>
                  )}
                </div>
              </div>

              {/* Grid of Cards */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
                gap: '14px',
              }}>
                {filteredTables.map((tbl) => {
                  const isSelected = selectedTable?.id === tbl.id;
                  return (
                    <div
                      key={tbl.id}
                      onClick={() => setSelectedTable(tbl)}
                      className="white-card"
                      style={{
                        padding: '16px',
                        cursor: 'pointer',
                        border: isSelected ? '2px solid var(--accent-primary)' : '1px solid var(--border-subtle)',
                        background: isSelected ? '#f0f7ff' : '#ffffff',
                        position: 'relative',
                        transform: isSelected ? 'translateY(-2px)' : 'none',
                        boxShadow: isSelected ? 'var(--shadow-md)' : 'var(--shadow-sm)',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
                        <div>
                          <div style={{ fontSize: '1.2rem', fontWeight: 800, color: 'var(--text-main)', lineHeight: 1.1 }}>
                            {tbl.code}
                          </div>
                          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                            {tbl.section}
                          </div>
                        </div>

                        <span className={`badge ${
                          tbl.status === 'VACANT' ? 'badge-vacant' :
                          tbl.status === 'OCCUPIED' ? 'badge-occupied' :
                          tbl.status === 'ATTENDED' ? 'badge-attended' :
                          tbl.status === 'FOOD_DELIVERED' ? 'badge-food' :
                          tbl.status === 'CLEANING_REQUIRED' ? 'badge-cleaning' : 'badge-warning'
                        }`}>
                          {tbl.status === 'VACANT' ? 'Ready' :
                           tbl.status === 'OCCUPIED' ? 'Seated' :
                           tbl.status === 'ATTENDED' ? 'Attended' :
                           tbl.status === 'FOOD_DELIVERED' ? 'Served' :
                           tbl.status === 'CLEANING_REQUIRED' ? 'Bussing' : tbl.status}
                        </span>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.78rem', marginTop: '12px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '5px', color: 'var(--text-muted)' }}>
                          <Users size={13} />
                          <span>{tbl.customerCount > 0 ? `${tbl.customerCount}/${tbl.capacity} guests` : `0/${tbl.capacity} seats`}</span>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.74rem', color: 'var(--text-dim)' }}>
                          <Clock size={12} />
                          <span>{tbl.lastStateChangeAt}</span>
                        </div>
                      </div>

                      {tbl.hasActiveAlert && (
                        <div style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                          padding: '4px 8px',
                          borderRadius: 'var(--radius-sm)',
                          background: '#fef2f2',
                          color: '#b91c1c',
                          fontSize: '0.72rem',
                          fontWeight: 600,
                          marginTop: '10px',
                          border: '1px solid #fecaca',
                        }}>
                          <AlertTriangle size={12} />
                          <span>Attention Required</span>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Active Operational Alerts List */}
          <div className="white-card" style={{ padding: '20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <AlertTriangle size={18} color="var(--status-critical)" />
                <h3 style={{ fontSize: '0.98rem', fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>
                  Active Floor & Service Alerts
                </h3>
              </div>
              <span className={`badge ${alerts.length > 0 ? 'badge-critical' : 'badge-vacant'}`}>
                {alerts.length} Active
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {alerts.map((alt) => (
                <div
                  key={alt.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '12px 16px',
                    background: '#fef2f2',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid #fecaca',
                    flexWrap: 'wrap',
                    gap: '12px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <span className={`badge ${alt.severity === 'CRITICAL' ? 'badge-critical' : 'badge-warning'}`}>
                      {alt.severity}
                    </span>

                    <div>
                      <div style={{ fontSize: '0.86rem', fontWeight: 700, color: '#991b1b' }}>
                        [{alt.tableCode}] {alt.message}
                      </div>
                      <div style={{ fontSize: '0.72rem', color: '#b91c1c' }}>
                        Triggered {alt.triggeredAt} • Immediate floor action needed
                      </div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {!alt.isAcknowledged && (
                      <button
                        onClick={() => handleAcknowledgeAlert(alt.id)}
                        style={{
                          padding: '6px 12px',
                          borderRadius: 'var(--radius-sm)',
                          background: '#ffffff',
                          color: '#b45309',
                          border: '1px solid #fde68a',
                          fontSize: '0.75rem',
                          fontWeight: 600,
                          boxShadow: 'var(--shadow-sm)',
                        }}
                      >
                        Acknowledge
                      </button>
                    )}

                    <button
                      onClick={() => handleResolveAlert(alt.id)}
                      style={{
                        padding: '6px 12px',
                        borderRadius: 'var(--radius-sm)',
                        background: '#059669',
                        color: '#ffffff',
                        border: 'none',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        boxShadow: 'var(--shadow-sm)',
                      }}
                    >
                      Resolve
                    </button>
                  </div>
                </div>
              ))}

              {alerts.length === 0 && (
                <div style={{
                  padding: '24px 16px',
                  textAlign: 'center',
                  background: '#f8fafc',
                  borderRadius: 'var(--radius-md)',
                  border: '1px dashed var(--border-medium)',
                  color: 'var(--text-muted)',
                  fontSize: '0.84rem',
                }}>
                  <CheckCircle2 size={24} color="var(--status-vacant)" style={{ margin: '0 auto 6px auto', display: 'block' }} />
                  <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>All Floor Timers Within Target Limits</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', marginTop: '2px' }}>
                    No tables currently exceeding attendance or food delivery thresholds.
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right Side: Selected Table Operational Control Drawer */}
        <div className="white-card" style={{ padding: '20px', position: 'sticky', top: '80px' }}>
          {selectedTable ? (
            <div>
              {/* Table Header Banner */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                paddingBottom: '14px',
                borderBottom: '1px solid var(--border-subtle)',
                marginBottom: '16px',
              }}>
                <div>
                  <div style={{ fontSize: '1.3rem', fontWeight: 800, color: 'var(--text-main)', lineHeight: 1.1 }}>
                    Table {selectedTable.code}
                  </div>
                  <div style={{ fontSize: '0.76rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                    {selectedTable.section} • Capacity: {selectedTable.capacity} Seats
                  </div>
                </div>

                <span className={`badge ${
                  selectedTable.status === 'VACANT' ? 'badge-vacant' :
                  selectedTable.status === 'OCCUPIED' ? 'badge-occupied' :
                  selectedTable.status === 'ATTENDED' ? 'badge-attended' :
                  selectedTable.status === 'FOOD_DELIVERED' ? 'badge-food' :
                  selectedTable.status === 'CLEANING_REQUIRED' ? 'badge-cleaning' : 'badge-warning'
                }`}>
                  {selectedTable.status === 'VACANT' ? 'Ready' :
                   selectedTable.status === 'OCCUPIED' ? 'Seated' :
                   selectedTable.status === 'ATTENDED' ? 'Attended' :
                   selectedTable.status === 'FOOD_DELIVERED' ? 'Served' :
                   selectedTable.status === 'CLEANING_REQUIRED' ? 'Needs Bussing' : selectedTable.status}
                </span>
              </div>

              {/* Action Feedback Notification */}
              {actionFeedback && (
                <div style={{
                  padding: '9px 12px',
                  borderRadius: 'var(--radius-md)',
                  marginBottom: '14px',
                  background: actionFeedback.success ? '#ecfdf5' : '#fef2f2',
                  color: actionFeedback.success ? '#065f46' : '#991b1b',
                  border: `1px solid ${actionFeedback.success ? '#a7f3d0' : '#fecaca'}`,
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}>
                  {actionFeedback.success ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}
                  <span>{actionFeedback.message}</span>
                </div>
              )}

              {/* Service Timers & Assigned Staff */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '8px',
                background: '#f8fafc',
                padding: '10px 12px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-subtle)',
                marginBottom: '16px',
                fontSize: '0.76rem',
              }}>
                <div>
                  <div style={{ color: 'var(--text-dim)', fontSize: '0.7rem' }}>Assigned Waiter</div>
                  <div style={{ fontWeight: 600, color: 'var(--text-main)', marginTop: '2px' }}>
                    {selectedTable.assignedWaiter || 'Sam Waiter'}
                  </div>
                </div>

                <div>
                  <div style={{ color: 'var(--text-dim)', fontSize: '0.7rem' }}>Last Interaction</div>
                  <div style={{ fontWeight: 600, color: 'var(--text-main)', marginTop: '2px' }}>
                    {selectedTable.lastStateChangeAt || 'Active'}
                  </div>
                </div>
              </div>

              {/* Quick Guest Headcount & Paging Control */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '18px',
                padding: '10px 12px',
                background: '#f1f5f9',
                borderRadius: 'var(--radius-md)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Users size={15} color="var(--text-muted)" />
                  <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-main)' }}>
                    Party Size: {selectedTable.customerCount || 0}
                  </span>
                  {selectedTable.status !== 'VACANT' && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginLeft: '4px' }}>
                      <button
                        onClick={() => handleAdjustGuestCount(-1)}
                        title="Decrease party count"
                        style={{
                          width: '22px',
                          height: '22px',
                          borderRadius: '4px',
                          background: '#ffffff',
                          border: '1px solid var(--border-medium)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: 'var(--text-main)',
                        }}
                      >
                        <Minus size={11} />
                      </button>
                      <button
                        onClick={() => handleAdjustGuestCount(1)}
                        title="Increase party count"
                        style={{
                          width: '22px',
                          height: '22px',
                          borderRadius: '4px',
                          background: '#ffffff',
                          border: '1px solid var(--border-medium)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: 'var(--text-main)',
                        }}
                      >
                        <Plus size={11} />
                      </button>
                    </div>
                  )}
                </div>

                <button
                  onClick={handlePageWaiter}
                  title="Send audio notification to assigned staff"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '5px',
                    padding: '5px 10px',
                    background: '#ffffff',
                    border: '1px solid var(--border-medium)',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '0.74rem',
                    fontWeight: 600,
                    color: 'var(--accent-primary)',
                    boxShadow: 'var(--shadow-sm)',
                  }}
                >
                  <BellRing size={13} />
                  <span>Page Waiter</span>
                </button>
              </div>

              {/* One-Click Fast Turnaround Actions */}
              <div style={{ marginBottom: '20px' }}>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', fontWeight: 700, textTransform: 'uppercase', marginBottom: '8px', letterSpacing: '0.04em' }}>
                  Floor Actions ({currentActor.role})
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {/* Seating form when VACANT */}
                  {selectedTable.status === 'VACANT' && (
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <select
                        value={guestCountInput}
                        onChange={(e) => setGuestCountInput(Number(e.target.value))}
                        style={{ width: '110px', fontSize: '0.8rem' }}
                      >
                        {[1, 2, 3, 4, 5, 6, 8].map(n => (
                          <option key={n} value={n}>{n} Guests</option>
                        ))}
                      </select>

                      <button
                        disabled={isSubmittingAction}
                        onClick={handleSeatWalkIn}
                        style={{
                          flex: 1,
                          padding: '10px 14px',
                          background: 'var(--accent-primary)',
                          borderRadius: 'var(--radius-md)',
                          color: '#ffffff',
                          fontSize: '0.82rem',
                          fontWeight: 600,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          gap: '6px',
                          boxShadow: 'var(--shadow-sm)',
                        }}
                      >
                        <Users size={15} />
                        <span>Seat Walk-in Party</span>
                      </button>
                    </div>
                  )}

                  {/* Attendance Confirmation Button */}
                  {selectedTable.status !== 'VACANT' && selectedTable.status !== 'CLEANING_REQUIRED' && (
                    <button
                      disabled={isSubmittingAction}
                      onClick={handleConfirmAttendance}
                      style={{
                        width: '100%',
                        padding: '10px 14px',
                        background: '#f0fdfa',
                        border: '1px solid #99f6e4',
                        borderRadius: 'var(--radius-md)',
                        color: '#0f766e',
                        fontSize: '0.82rem',
                        fontWeight: 600,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '6px',
                        boxShadow: 'var(--shadow-sm)',
                      }}
                    >
                      <CheckCircle2 size={15} />
                      <span>Mark Greeted & Ordered</span>
                    </button>
                  )}

                  {/* Food Delivery Form */}
                  {selectedTable.status !== 'VACANT' && selectedTable.status !== 'CLEANING_REQUIRED' && (
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <select
                        value={deliveryCourse}
                        onChange={(e) => setDeliveryCourse(e.target.value)}
                        style={{ flex: 1, fontSize: '0.78rem' }}
                      >
                        <option value="Appetizers">Appetizers</option>
                        <option value="Mains">Mains</option>
                        <option value="Desserts">Desserts</option>
                        <option value="Drinks">Drinks</option>
                      </select>

                      <select
                        value={deliveryBatch}
                        onChange={(e) => setDeliveryBatch(Number(e.target.value))}
                        style={{ width: '85px', fontSize: '0.78rem' }}
                      >
                        <option value={1}>Batch 1</option>
                        <option value={2}>Batch 2</option>
                        <option value={3}>Batch 3</option>
                      </select>

                      <button
                        disabled={isSubmittingAction}
                        onClick={handleConfirmFoodDelivery}
                        style={{
                          padding: '10px 14px',
                          background: '#f5f3ff',
                          border: '1px solid #ddd6fe',
                          borderRadius: 'var(--radius-md)',
                          color: '#6d28d9',
                          fontSize: '0.82rem',
                          fontWeight: 600,
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                          boxShadow: 'var(--shadow-sm)',
                        }}
                      >
                        <Utensils size={14} />
                        <span>Served</span>
                      </button>
                    </div>
                  )}

                  {/* Departure Button */}
                  {selectedTable.status !== 'VACANT' && selectedTable.status !== 'CLEANING_REQUIRED' && (
                    <button
                      disabled={isSubmittingAction}
                      onClick={handleDepartParty}
                      style={{
                        width: '100%',
                        padding: '9px 14px',
                        background: '#fff1f2',
                        border: '1px solid #fecdd3',
                        borderRadius: 'var(--radius-md)',
                        color: '#be123c',
                        fontSize: '0.8rem',
                        fontWeight: 600,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '6px',
                      }}
                    >
                      <RotateCcw size={14} />
                      <span>Party Departed (Mark for Bussing)</span>
                    </button>
                  )}

                  {/* Sanitize & Ready Button */}
                  {selectedTable.status === 'CLEANING_REQUIRED' && (
                    <button
                      disabled={isSubmittingAction}
                      onClick={handleSanitizeAndReset}
                      style={{
                        width: '100%',
                        padding: '11px 14px',
                        background: '#059669',
                        border: 'none',
                        borderRadius: 'var(--radius-md)',
                        color: '#ffffff',
                        fontSize: '0.84rem',
                        fontWeight: 600,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '6px',
                        boxShadow: 'var(--shadow-sm)',
                      }}
                    >
                      <Sparkles size={16} />
                      <span>Sanitize & Set Table Ready</span>
                    </button>
                  )}
                </div>
              </div>

              {/* Live CCTV Table Section Peek */}
              <div style={{
                marginBottom: '20px',
                padding: '12px',
                background: '#f8fafc',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-subtle)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.74rem', fontWeight: 600, color: 'var(--text-main)' }}>
                    <Camera size={14} color="var(--accent-primary)" />
                    <span>Zone Camera Feed</span>
                  </div>
                  <span style={{ fontSize: '0.68rem', color: 'var(--status-vacant)', fontWeight: 600 }}>● Online</span>
                </div>

                <div style={{
                  position: 'relative',
                  width: '100%',
                  height: '110px',
                  borderRadius: 'var(--radius-sm)',
                  overflow: 'hidden',
                  background: '#0f172a',
                }}>
                  <img
                    src={`/api/v1/cameras/cam-01/snapshot?processed=false`}
                    alt="Table zone CCTV"
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                    onError={(e) => {
                      (e.target as HTMLImageElement).src = '/sample_cctv_raw.jpg';
                    }}
                  />
                  <div style={{
                    position: 'absolute',
                    bottom: '4px',
                    left: '6px',
                    background: 'rgba(0,0,0,0.6)',
                    color: '#ffffff',
                    fontSize: '0.64rem',
                    padding: '2px 6px',
                    borderRadius: '4px',
                  }}>
                    CAM-01 • {selectedTable.section}
                  </div>
                </div>
              </div>

              {/* Service Event History Timeline */}
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    Session Timeline
                  </div>
                  {isLoadingTimeline && <span style={{ fontSize: '0.68rem', color: 'var(--text-dim)' }}>Loading...</span>}
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {timeline.map((ev, idx) => (
                    <div key={ev.id || idx} style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
                      <div style={{
                        width: '20px',
                        height: '20px',
                        borderRadius: '50%',
                        background: '#eff6ff',
                        border: '1px solid #bfdbfe',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                        marginTop: '1px',
                        color: 'var(--accent-primary)',
                      }}>
                        <CheckCircle2 size={11} />
                      </div>

                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                          <span style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-main)' }}>
                            {ev.displayName}
                          </span>
                          <span style={{ fontSize: '0.68rem', color: 'var(--text-dim)' }}>
                            {ev.relativeTime || 'Recently'}
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}

                  {timeline.length === 0 && (
                    <div style={{ padding: '14px', textAlign: 'center', color: 'var(--text-dim)', fontSize: '0.75rem', background: '#f8fafc', borderRadius: 'var(--radius-sm)' }}>
                      No service events recorded for this session yet.
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div style={{ padding: '40px 20px', textAlign: 'center', color: 'var(--text-dim)' }}>
              Select a table from the floor layout to view details and service controls.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
