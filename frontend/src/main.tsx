import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

type Client = { id: number; name: string; company?: string; manager?: string; phone?: string; email?: string; trade_place?: string; birth_date?: string; status: ClientStatus };
type ClientStatus = 'active' | 'archived' | 'out_of_stock';
type MainTab = 'registry' | 'settings';
type HelpTab = 'features' | 'manual' | 'journal';
type FilterOptions = { managers: string[]; price_types: string[]; buyer_types: string[]; counterparty_types: string[] };
type LogEntry = { id: string; created_at?: string; source: string; level: string; process: string; row_number?: number; message: string };

const formatMoscowTime = (value?: string) => {
  if (!value) return '—';
  const normalized = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value) ? value : `${value}Z`;
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? value : `${new Intl.DateTimeFormat('ru-RU', { timeZone: 'Europe/Moscow', dateStyle: 'short', timeStyle: 'medium' }).format(date)} МСК`;
};

type ClientsHeaderProps = {
  activeTab: MainTab;
  onTabChange: (tab: MainTab) => void;
  query: string;
  onQueryChange: (query: string) => void;
};

const STATUS_LABELS: Record<ClientStatus, string> = {
  active: 'Активный',
  archived: 'Архивный',
  out_of_stock: 'Нет в наличии',
};
const trimSlash = (value: string) => value.replace(/\/$/, '');
const BASE_URL = import.meta.env.BASE_URL || '/';
const API_BASE_URL = trimSlash(import.meta.env.VITE_API_URL || `${BASE_URL}api`);

async function api(path: string, init?: RequestInit) {
  const response = await fetch(`${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`, init);
  if (!response.ok) {
    const body = await response.text();
    try { throw new Error(JSON.parse(body).detail || body); } catch (error) { if (error instanceof SyntaxError) throw new Error(body || `Ошибка HTTP ${response.status}`); throw error; }
  }
  return response.json();
}

function App() {
  const [activeTab, setActiveTab] = useState<MainTab>('registry');
  const [helpTab, setHelpTab] = useState<HelpTab>('features');
  const [clients, setClients] = useState<Client[]>([]);
  const [total, setTotal] = useState(0);
  const [q, setQ] = useState('');
  const [manager, setManager] = useState('');
  const [priceType, setPriceType] = useState('');
  const [hasPhone, setHasPhone] = useState('');
  const [hasEmail, setHasEmail] = useState('');
  const [buyerType, setBuyerType] = useState('');
  const [counterpartyType, setCounterpartyType] = useState('');
  const [filterOptions, setFilterOptions] = useState<FilterOptions>({ managers: [], price_types: [], buyer_types: [], counterparty_types: [] });
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState('100');
  const [detail, setDetail] = useState<any>(null);
  const [selectedClientId, setSelectedClientId] = useState<number | null>(null);
  const [checkedIds, setCheckedIds] = useState<Set<number>>(new Set());
  const [notice, setNotice] = useState('');
  const [uploading, setUploading] = useState(false);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadLogs = async () => {
    setLogsLoading(true);
    try { setLogs(await api('/logs?limit=2000')); }
    catch (error) { setNotice(`Не удалось загрузить журнал: ${error instanceof Error ? error.message : String(error)}`); }
    finally { setLogsLoading(false); }
  };

  const filterQuery = useMemo(() => {
    const params = new URLSearchParams();
    if (q) params.set('search', q);
    if (manager) params.set('manager', manager);
    if (priceType) params.set('price_type', priceType);
    if (hasPhone) params.set('has_phone', hasPhone);
    if (hasEmail) params.set('has_email', hasEmail);
    if (buyerType) params.set('buyer_type', buyerType);
    if (counterpartyType) params.set('counterparty_type', counterpartyType);
    return params.toString();
  }, [q, manager, priceType, hasPhone, hasEmail, buyerType, counterpartyType]);
  const query = useMemo(() => {
    const params = new URLSearchParams(filterQuery);
    params.set('page', String(page));
    params.set('page_size', pageSize);
    return params.toString();
  }, [filterQuery, page, pageSize]);
  const exportUrl = `${API_BASE_URL}/clients-export.xlsx${filterQuery ? `?${filterQuery}` : ''}`;
  const load = () => api(`/clients?${query}`).then(d => { setClients(d.items); setTotal(d.total); });
  const visibleIds = useMemo(() => clients.map(client => client.id), [clients]);
  const allVisibleChecked = visibleIds.length > 0 && visibleIds.every(id => checkedIds.has(id));
  const toggleClientCheck = (clientId: number) => setCheckedIds(previous => { const next = new Set(previous); next.has(clientId) ? next.delete(clientId) : next.add(clientId); return next; });
  const toggleVisibleCheck = () => setCheckedIds(previous => { const next = new Set(previous); allVisibleChecked ? visibleIds.forEach(id => next.delete(id)) : visibleIds.forEach(id => next.add(id)); return next; });
  const deleteCheckedClients = async () => {
    const ids = [...checkedIds];
    if (!ids.length) return;
    if (!window.confirm(`Удалить выбранные строки: ${ids.length}? Действие нельзя отменить.`)) return;
    const result = await api(`/clients?ids=${ids.join(',')}`, { method: 'DELETE' });
    setNotice(`Удалено строк: ${result.deleted}`);
    setCheckedIds(new Set());
    if (selectedClientId && ids.includes(selectedClientId)) { setSelectedClientId(null); setDetail(null); }
    load();
  };
  const pageSizeNumber = pageSize === 'all' ? Math.max(total, 1) : Number(pageSize);
  const totalPages = pageSize === 'all' ? 1 : Math.ceil(total / pageSizeNumber) || 1;
  const resetFilters = () => { setQ(''); setPriceType(''); setBuyerType(''); setCounterpartyType(''); setManager(''); setHasPhone(''); setHasEmail(''); setPage(1); };

  useEffect(() => { if (activeTab === 'registry') load(); }, [query, activeTab]);
  useEffect(() => { api('/clients-filter-options').then(setFilterOptions); }, []);
  useEffect(() => { if (activeTab === 'settings') loadLogs(); }, [activeTab]);

  const upload = async (files: FileList | null) => {
    if (!files?.length) return;
    const fileNames = [...files].map(file => file.name).join(', ');
    const fd = new FormData();
    [...files].forEach(f => fd.append('files', f));
    setUploading(true);
    setNotice(`Загрузка: ${fileNames}`);
    try {
      const r = await api('/imports', { method: 'POST', body: fd });
      setNotice(`${r.message}. Всего строк: ${r.rows}. Прочитано: ${r.read}. Добавлено: ${r.added}. Обновлено: ${r.updated}. Пропущено: ${r.skipped}. Ошибок: ${r.errors}`);
      setHelpTab('journal');
      await Promise.all([load(), loadLogs()]);
    } catch (error) {
      setNotice(`Ошибка загрузки «${fileNames}»: ${error instanceof Error ? error.message : String(error)}`);
      setHelpTab('journal');
      await loadLogs();
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  return <main>
    <input ref={fileInputRef} className="hidden-file" type="file" multiple accept=".xls,.xlsx" onChange={e => upload(e.target.files)} />
    <ClientsHeader
      activeTab={activeTab}
      onTabChange={setActiveTab}
      query={q}
      onQueryChange={value => { setQ(value); setPage(1); }}
    />
    {activeTab === 'settings' ? <Settings active={helpTab} onChange={setHelpTab} onUpload={() => fileInputRef.current?.click()} notice={notice} uploading={uploading} logs={logs} logsLoading={logsLoading} onRefreshLogs={loadLogs} /> : <>
      {notice && <div className="notice">{notice}</div>}
      <div className="workspace"><aside className="filter-card"><div className="filter-card-header"><div><p className="eyebrow">Фильтры</p><h2>Реестр</h2></div><span className="chip">{total} строк</span></div><button className="tonal" type="button" onClick={resetFilters}>Сбросить фильтры</button><div className="divider" /><div className="filter-stack"><label>Тип цены<select aria-label="Тип цены" value={priceType} onChange={e => { setPriceType(e.target.value); setPage(1); }}><option value="">Все типы цены</option>{filterOptions.price_types.map(value => <option key={value} value={value}>{value}</option>)}</select></label><label>Вид покупателя<select aria-label="Вид покупателя" value={buyerType} onChange={e => { setBuyerType(e.target.value); setPage(1); }}><option value="">Все виды покупателей</option>{filterOptions.buyer_types.map(value => <option key={value} value={value}>{value}</option>)}</select></label><label>Вид контрагента<select aria-label="Вид контрагента" value={counterpartyType} onChange={e => { setCounterpartyType(e.target.value); setPage(1); }}><option value="">Все виды контрагентов</option>{filterOptions.counterparty_types.map(value => <option key={value} value={value}>{value}</option>)}</select></label><label>Менеджер<select aria-label="Менеджер" value={manager} onChange={e => { setManager(e.target.value); setPage(1); }}><option value="">Все менеджеры</option>{filterOptions.managers.map(value => <option key={value} value={value}>{value}</option>)}</select></label><label>Телефон<select aria-label="Наличие телефона" value={hasPhone} onChange={e => { setHasPhone(e.target.value); setPage(1); }}><option value="">Все</option><option value="true">Есть</option><option value="false">Нет</option></select></label><label>Email<select aria-label="Наличие Email" value={hasEmail} onChange={e => { setHasEmail(e.target.value); setPage(1); }}><option value="">Все</option><option value="true">Есть</option><option value="false">Нет</option></select></label></div></aside><section className="content-area"><div className="registry-summary"><span>В реестре: <b>{total}</b> строк</span><div className="summary-actions">{checkedIds.size > 0 && <button className="danger-action" type="button" onClick={deleteCheckedClients}>Удалить выбранные ({checkedIds.size})</button>}<a className="button tonal" href={exportUrl}>Скачать</a></div></div><section className="table"><table><thead><tr><th className="check-cell"><input type="checkbox" aria-label="Выбрать все строки на странице" checked={allVisibleChecked} onChange={toggleVisibleCheck} /></th><th>Наименование</th><th>Фирма</th><th>Менеджер</th><th>Телефоны</th></tr></thead><tbody>{clients.map(c => <tr key={c.id} className={[c.status === 'out_of_stock' ? 'muted-row' : '', selectedClientId === c.id ? 'selected-row' : '', checkedIds.has(c.id) ? 'checked-row' : ''].filter(Boolean).join(' ')} aria-selected={selectedClientId === c.id} onClick={() => { setSelectedClientId(c.id); api(`/clients/${c.id}`).then(setDetail); }}><td className="check-cell"><input type="checkbox" aria-label={`Выбрать ${c.name}`} checked={checkedIds.has(c.id)} onClick={event => event.stopPropagation()} onChange={() => toggleClientCheck(c.id)} /></td><td><b>{c.name}</b></td><td>{c.company}</td><td>{c.manager}</td><td>{c.phone}</td></tr>)}</tbody></table><footer><button disabled={page === 1} onClick={() => setPage(page - 1)}>Назад</button><span>{page} / {totalPages} · {total} записей</span><label className="page-size">Строк на странице<select value={pageSize} onChange={e => { setPageSize(e.target.value); setPage(1); }}><option value="100">100</option><option value="200">200</option><option value="300">300</option><option value="400">400</option><option value="500">500</option><option value="all">Все</option></select></label><button disabled={pageSize === 'all' || page * pageSizeNumber >= total} onClick={() => setPage(page + 1)}>Вперед</button></footer></section></section></div>{detail && <div className="drawer-backdrop" onClick={() => setDetail(null)}><aside className="drawer" onClick={event => event.stopPropagation()}><button className="drawer-close" type="button" onClick={() => setDetail(null)}>×</button><ClientCard c={detail} /></aside></div>}
    </>}
  </main>;
}

function ClientsHeader({ activeTab, onTabChange, query, onQueryChange }: ClientsHeaderProps) {
  return <div className="page-header">
    <header className="topbar">
      <nav className="tabs" aria-label="Основная навигация">
        <a href="https://kvasmix.ru/vr/catalog/">Каталог</a>
        <button type="button" className={activeTab === 'registry' ? 'selected' : ''} aria-current={activeTab === 'registry' ? 'page' : undefined} onClick={() => onTabChange('registry')}>Контрагенты</button>
        <button type="button" className={activeTab === 'settings' ? 'selected' : ''} aria-current={activeTab === 'settings' ? 'page' : undefined} onClick={() => onTabChange('settings')}>Настройки</button>
      </nav>
    </header>
    {activeTab === 'registry' && <SearchBar value={query} onChange={onQueryChange} />}
  </div>;
}

function SearchBar({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return <section className="search-paper" role="search">
    <svg className="search-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="m21 21-4.35-4.35m2.35-5.65a8 8 0 1 1-16 0 8 8 0 0 1 16 0Z" /></svg>
    <input className="search" type="search" aria-label="Поиск контрагентов" placeholder="Поиск по клиентам, email, телефонам, фирме..." value={value} onChange={event => onChange(event.target.value)} />
  </section>;
}
function Settings({ active, onChange, onUpload, notice, uploading, logs, logsLoading, onRefreshLogs }: { active: HelpTab; onChange: (tab: HelpTab) => void; onUpload: () => void; notice: string; uploading: boolean; logs: LogEntry[]; logsLoading: boolean; onRefreshLogs: () => void }) {
  const updateCommand = '/var/www/html/vr/clients/update.sh';
  const copyUpdateCommand = async () => {
    await navigator.clipboard.writeText(updateCommand);
  };
  return <section className="help card"><div className="settings-heading"><h2>Настройки</h2><button className="primary-action" disabled={uploading} onClick={onUpload}>{uploading ? 'Загрузка…' : 'Загрузить XLS'}</button></div>{notice && <div className="notice" role="status">{notice}</div>}<div className="subtabs"><button className={active === 'features' ? 'selected' : ''} onClick={() => onChange('features')}>Описание и возможности</button><button className={active === 'manual' ? 'selected' : ''} onClick={() => onChange('manual')}>Инструкция для пользователя</button><button className={active === 'journal' ? 'selected' : ''} onClick={() => onChange('journal')}>Журнал загрузки</button></div>{active !== 'journal' && <div className="copy-row"><textarea readOnly value={updateCommand} aria-label="Команда обновления проекта" /><button title="Копировать в буфер обмена" onClick={copyUpdateCommand}>📋</button></div>}{active === 'features' ? <div><h3>Описание и возможности</h3><ul><li>Импорт клиентов из файлов Excel `.xls` и `.xlsx`.</li><li>Поиск по наименованию, фирме, контактам, email, телефонам и местам торговли.</li><li>Экспорт списка клиентов в Excel.</li><li>Статус «Нет в наличии» всегда отображается в конце реестра.</li></ul></div> : active === 'manual' ? <div><h3>Инструкция для пользователя</h3><ol><li>Откройте вкладку «Настройки» и нажмите кнопку «Загрузить XLS».</li><li>Выберите один или несколько файлов `.xls` или `.xlsx`.</li><li>Дождитесь отчета о добавленных, обновленных, пропущенных строках и ошибках.</li><li>Используйте поиск для быстрого отбора клиентов.</li><li>Кликните по строке, чтобы открыть карточку клиента.</li></ol></div> : <UploadJournal logs={logs} loading={logsLoading} onRefresh={onRefreshLogs} />}</section>;
}

function UploadJournal({ logs, loading, onRefresh }: { logs: LogEntry[]; loading: boolean; onRefresh: () => void }) {
  return <section className="upload-journal"><div className="journal-heading"><div><h3>Журнал загрузки</h3><p>События импорта, выполненные действия и подробные ошибки обработки файлов. Время указано по Москве (UTC+3).</p></div><button className="tonal" type="button" disabled={loading} onClick={onRefresh}>{loading ? 'Обновление…' : 'Обновить'}</button></div>{!loading && logs.length === 0 ? <p className="empty-state">Событий пока нет.</p> : <div className="journal-table"><table><thead><tr><th>Дата (МСК)</th><th>Источник</th><th>Процесс</th><th>Строка</th><th>Описание и способ исправления</th></tr></thead><tbody>{logs.map(entry => <tr key={entry.id} className={`log-${entry.level}`}><td>{formatMoscowTime(entry.created_at)}</td><td><span className="log-level">{entry.level === 'error' ? 'Ошибка' : entry.level === 'warning' ? 'Предупреждение' : entry.source}</span></td><td>{entry.process || '—'}</td><td>{entry.row_number ?? '—'}</td><td>{entry.message || 'Описание отсутствует'}</td></tr>)}</tbody></table></div>}</section>;
}
function ClientCard({ c }: { c: any }) { const phones = c.phones || []; return <div className="card"><h2>{c.name}</h2><Block title="Все поля XLS" rows={[["Наименование", c.name], ["Тип цены", c.price_type], ["Менеджер", c.manager], ["Дата рождения", c.birth_date], ["Email", c.emails?.join(', ')], ["Телефоны прочие", c.raw_common_phones || phones.filter((p: any) => p.type === 'common').map((p: any) => p.phone).join(', ')], ["Места торговли", c.trade_places?.join(', ')], ["Телефоны для СМС и рассылки", c.raw_sms_phones || phones.filter((p: any) => p.type === 'sms').map((p: any) => p.phone).join(', ')], ["Руководитель", c.director], ["Фирма", c.company], ["Контактное лицо", c.contact_person], ["Источник клиента", c.client_source], ["Дата последней покупки", c.last_purchase_date], ["Вид покупателя", c.buyer_type], ["Вид контрагента", c.counterparty_type]]} /></div>; }
function Block({ title, rows }: any) { return <section><h3>{title}</h3>{rows.map((r: any) => <p key={r[0]}><b>{r[0]}:</b> {r[1] || '—'}</p>)}</section>; }
createRoot(document.getElementById('root')!).render(<App />);
