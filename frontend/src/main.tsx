import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

type Client = { id: number; name: string; company?: string; manager?: string; phone?: string; email?: string; trade_place?: string; birth_date?: string; status: ClientStatus };
type ClientStatus = 'active' | 'archived' | 'out_of_stock';
type MainTab = 'registry' | 'settings';
type HelpTab = 'features' | 'manual' | 'autoload' | 'journal';
type PresenceFilter = '' | 'true' | 'false';
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
  onOpenFilters: () => void;
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
    if (response.status === 504) throw new Error('Сервис не успел ответить. Повторите попытку через несколько секунд.');
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      try { throw new Error(JSON.parse(body).detail || `Ошибка HTTP ${response.status}`); } catch (error) { if (!(error instanceof SyntaxError)) throw error; }
    }
    const plainText = body.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
    throw new Error(plainText && plainText.length < 300 ? plainText : `Ошибка HTTP ${response.status}`);
  }
  return response.json();
}

function App() {
  const [activeTab, setActiveTab] = useState<MainTab>('registry');
  const [helpTab, setHelpTab] = useState<HelpTab>('features');
  const [clients, setClients] = useState<Client[]>([]);
  const [total, setTotal] = useState(0);
  const [q, setQ] = useState('');
  const [phoneQuery, setPhoneQuery] = useState('');
  const [manager, setManager] = useState<string[]>([]);
  const [priceType, setPriceType] = useState<string[]>([]);
  const [hasPhone, setHasPhone] = useState<PresenceFilter>('true');
  const [hasEmail, setHasEmail] = useState<PresenceFilter>('');
  const [buyerType, setBuyerType] = useState<string[]>([]);
  const [counterpartyType, setCounterpartyType] = useState<string[]>([]);
  const [filtersOpen, setFiltersOpen] = useState(false);
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
  const [logSource, setLogSource] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadLogs = async (source = logSource) => {
    setLogsLoading(true);
    try { setLogs(await api(`/logs${source ? `?source=${encodeURIComponent(source)}` : ''}`)); }
    catch (error) { setNotice(`Не удалось загрузить журнал: ${error instanceof Error ? error.message : String(error)}`); }
    finally { setLogsLoading(false); }
  };

  const openFtpLogs = async () => {
    setLogSource('FTP');
    setHelpTab('journal');
    await loadLogs('FTP');
  };

  const showAllLogs = async () => {
    setLogSource('');
    await loadLogs('');
  };

  const deleteLogs = async () => {
    if (!window.confirm('Удалить все события журнала? Действие нельзя отменить.')) return;
    try {
      const result = await api('/logs', { method: 'DELETE' });
      setLogs([]);
      setNotice(`Журнал очищен. Удалено событий: ${result.deleted}.`);
    } catch (error) {
      setNotice(`Не удалось очистить журнал: ${error instanceof Error ? error.message : String(error)}`);
    }
  };

  const deleteAllClients = async () => {
    if (!window.confirm('Удалить все строки реестра и связанные с ними данные? Действие нельзя отменить.')) return;
    try {
      const result = await api('/clients?all=true', { method: 'DELETE' });
      setClients([]);
      setTotal(0);
      setCheckedIds(new Set());
      setSelectedClientId(null);
      setDetail(null);
      setPage(1);
      setNotice(`Все строки реестра удалены. Удалено клиентов: ${result.deleted}.`);
    } catch (error) {
      setNotice(`Не удалось удалить строки реестра: ${error instanceof Error ? error.message : String(error)}`);
    }
  };

  const filterQuery = useMemo(() => {
    const params = new URLSearchParams();
    if (q) params.set('search', q);
    if (phoneQuery) params.set('phone_search', phoneQuery);
    manager.forEach(value => params.append('manager', value));
    priceType.forEach(value => params.append('price_type', value));
    buyerType.forEach(value => params.append('buyer_type', value));
    counterpartyType.forEach(value => params.append('counterparty_type', value));
    if (hasPhone) params.set('has_phone', hasPhone);
    if (hasEmail) params.set('has_email', hasEmail);
    return params.toString();
  }, [q, phoneQuery, manager, priceType, hasPhone, hasEmail, buyerType, counterpartyType]);
  const query = useMemo(() => {
    const params = new URLSearchParams(filterQuery);
    params.set('page', String(page));
    params.set('page_size', pageSize);
    return params.toString();
  }, [filterQuery, page, pageSize]);
  const exportUrl = `${API_BASE_URL}/clients-export.xlsx${filterQuery ? `?${filterQuery}` : ''}`;
  const load = (signal?: AbortSignal) => api(`/clients?${query}`, { signal }).then(d => { setClients(d.items); setTotal(d.total); });
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
  const resetFilters = () => { setQ(''); setPhoneQuery(''); setPriceType([]); setBuyerType([]); setCounterpartyType([]); setManager([]); setHasPhone('true'); setHasEmail(''); setPage(1); };

  useEffect(() => {
    if (activeTab !== 'registry') return;
    // При быстром переключении фильтров старый ответ не должен перезаписать
    // более свежий результат, в котором уже применён фильтр Email.
    const controller = new AbortController();
    load(controller.signal).catch(error => {
      if (error instanceof DOMException && error.name === 'AbortError') return;
      setNotice(`Не удалось загрузить реестр: ${error instanceof Error ? error.message : String(error)}`);
    });
    return () => controller.abort();
  }, [query, activeTab]);
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
      const accepted = await api('/imports', { method: 'POST', body: fd });
      let task = await api(`/imports/tasks/${accepted.task_id}`);
      while (task.status === 'accepted' || task.status === 'running') {
        const counters = task.total ? ` ${task.processed} / ${task.total} (${task.progress}%)` : '';
        setNotice(`${task.stage}${counters}`);
        await new Promise(resolve => window.setTimeout(resolve, 1500));
        task = await api(`/imports/tasks/${accepted.task_id}`);
      }
      if (task.status === 'failed') throw new Error(task.error || 'Неизвестная ошибка фонового импорта');
      const r = task.result;
      setNotice(`Импорт завершён. Всего строк: ${r.rows}. Прочитано: ${r.read}. Добавлено: ${r.added}. Обновлено: ${r.updated}. Пропущено: ${r.skipped}. Ошибок: ${r.errors}`);
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
      onOpenFilters={() => setFiltersOpen(true)}
    />
    {activeTab === 'settings' ? <Settings active={helpTab} onChange={setHelpTab} onUpload={() => fileInputRef.current?.click()} onDeleteAllClients={deleteAllClients} notice={notice} uploading={uploading} logs={logs} logsLoading={logsLoading} logSource={logSource} onRefreshLogs={() => loadLogs()} onShowAllLogs={showAllLogs} onOpenFtpLogs={openFtpLogs} onDeleteLogs={deleteLogs} /> : <>
      {notice && <div className="notice">{notice}</div>}
      <div className="workspace"><section className="content-area"><div className="registry-summary"><span>В реестре: <b>{total}</b> строк</span><div className="summary-actions">{checkedIds.size > 0 && <button className="danger-action" type="button" onClick={deleteCheckedClients}>Удалить выбранные ({checkedIds.size})</button>}<a className="button tonal" href={exportUrl}>Скачать</a></div></div><section className="table"><table><thead><tr><th className="check-cell"><input type="checkbox" aria-label="Выбрать все строки на странице" checked={allVisibleChecked} onChange={toggleVisibleCheck} /></th><th>Наименование</th><th>Фирма</th><th>Менеджер</th><th>Телефоны</th><th>Email</th></tr></thead><tbody>{clients.map(c => <tr key={c.id} className={[c.status === 'out_of_stock' ? 'muted-row' : '', selectedClientId === c.id ? 'selected-row' : '', checkedIds.has(c.id) ? 'checked-row' : ''].filter(Boolean).join(' ')} aria-selected={selectedClientId === c.id} onClick={() => { setSelectedClientId(c.id); api(`/clients/${c.id}`).then(setDetail); }}><td className="check-cell"><input type="checkbox" aria-label={`Выбрать ${c.name}`} checked={checkedIds.has(c.id)} onClick={event => event.stopPropagation()} onChange={() => toggleClientCheck(c.id)} /></td><td><b>{c.name}</b></td><td>{c.company}</td><td>{c.manager}</td><td>{c.phone}</td><td>{c.email}</td></tr>)}</tbody></table><footer><button disabled={page === 1} onClick={() => setPage(page - 1)}>Назад</button><span>{page} / {totalPages} · {total} записей</span><label className="page-size">Строк на странице<select value={pageSize} onChange={e => { setPageSize(e.target.value); setPage(1); }}><option value="100">100</option><option value="200">200</option><option value="300">300</option><option value="400">400</option><option value="500">500</option><option value="all">Все</option></select></label><button disabled={pageSize === 'all' || page * pageSizeNumber >= total} onClick={() => setPage(page + 1)}>Вперед</button></footer></section></section></div>      {filtersOpen && <FilterDialog q={q} phoneQuery={phoneQuery} hasPhone={hasPhone} hasEmail={hasEmail} manager={manager} priceType={priceType} buyerType={buyerType} counterpartyType={counterpartyType} options={filterOptions} onQ={setQ} onPhoneQuery={setPhoneQuery} onHasPhone={setHasPhone} onHasEmail={setHasEmail} onManager={setManager} onPriceType={setPriceType} onBuyerType={setBuyerType} onCounterpartyType={setCounterpartyType} onReset={resetFilters} onClose={() => { setFiltersOpen(false); setPage(1); }} />}
      {detail && <div className="drawer-backdrop" onClick={() => setDetail(null)}><aside className="drawer" onClick={event => event.stopPropagation()}><button className="drawer-close" type="button" onClick={() => setDetail(null)}>×</button><ClientCard c={detail} /></aside></div>}
    </>}
  </main>;
}

function ClientsHeader({ activeTab, onTabChange, query, onOpenFilters }: ClientsHeaderProps) {
  return <div className="page-header">
    <header className="topbar">
      <nav className="tabs" aria-label="Основная навигация">
        <a href="https://kvasmix.ru/vr/catalog/">Каталог</a>
        <button type="button" className={activeTab === 'registry' ? 'selected' : ''} aria-current={activeTab === 'registry' ? 'page' : undefined} onClick={() => onTabChange('registry')}>Контрагенты</button>
        <button type="button" className={activeTab === 'settings' ? 'selected' : ''} aria-current={activeTab === 'settings' ? 'page' : undefined} onClick={() => onTabChange('settings')}>Настройки</button>
      </nav>
    </header>
    {activeTab === 'registry' && <SearchBar value={query} onOpen={onOpenFilters} />}
  </div>;
}

function SearchBar({ value, onOpen }: { value: string; onOpen: () => void }) {
  return <button className="search-paper" type="button" aria-haspopup="dialog" onClick={onOpen}>
    <svg className="search-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="m21 21-4.35-4.35m2.35-5.65a8 8 0 1 1-16 0 8 8 0 0 1 16 0Z" /></svg>
    <span className={value ? 'search-value' : 'search-placeholder'}>{value || 'Поиск и фильтры'}</span>
  </button>;
}
type MultiFilterProps = { title: string; values: string[]; selected: string[]; onChange: (values: string[]) => void; searchable?: boolean };
function MultiFilter({ title, values, selected, onChange, searchable = false }: MultiFilterProps) {
  const [search, setSearch] = useState('');
  const toggle = (value: string) => onChange(selected.includes(value) ? selected.filter(item => item !== value) : [...selected, value]);
  const visibleValues = search ? values.filter(value => value.toLocaleLowerCase('ru').includes(search.toLocaleLowerCase('ru'))) : values;
  return <details className="filter-group"><summary><span>{title}</span>{selected.length > 0 && <span className="filter-count">{selected.length}</span>}</summary>{searchable && <input className="filter-search" type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder={`Поиск: ${title.toLocaleLowerCase('ru')}`} aria-label={`Поиск по значениям фильтра ${title}`} />}<div className="filter-values">{visibleValues.length ? visibleValues.map(value => <label key={value}><input type="checkbox" checked={selected.includes(value)} onChange={() => toggle(value)} />{value}</label>) : <p>Значения не найдены</p>}</div></details>;
}
function FilterDialog(props: { q: string; phoneQuery: string; hasPhone: PresenceFilter; hasEmail: PresenceFilter; manager: string[]; priceType: string[]; buyerType: string[]; counterpartyType: string[]; options: FilterOptions; onQ: (value: string) => void; onPhoneQuery: (value: string) => void; onHasPhone: (value: PresenceFilter) => void; onHasEmail: (value: PresenceFilter) => void; onManager: (value: string[]) => void; onPriceType: (value: string[]) => void; onBuyerType: (value: string[]) => void; onCounterpartyType: (value: string[]) => void; onReset: () => void; onClose: () => void }) {
  return <div className="filter-backdrop" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget) props.onClose(); }}><section className="filter-dialog" role="dialog" aria-modal="true" aria-labelledby="filter-title"><header><div><p className="eyebrow">Реестр</p><h2 id="filter-title">Поиск и фильтры</h2></div><button className="dialog-close" type="button" aria-label="Закрыть" onClick={props.onClose}>×</button></header><div className="filter-fields"><label>Поиск по наименованию<input autoFocus type="search" value={props.q} onChange={event => props.onQ(event.target.value)} placeholder="Введите наименование" /></label><label>Поиск по номеру телефона<input type="search" inputMode="tel" value={props.phoneQuery} onChange={event => props.onPhoneQuery(event.target.value)} placeholder="Введите номер телефона" /></label><label>Телефон<select value={props.hasPhone} onChange={event => props.onHasPhone(event.target.value as PresenceFilter)}><option value="true">Да</option><option value="false">Нет</option><option value="">Все</option></select></label><label>Email<select value={props.hasEmail} onChange={event => props.onHasEmail(event.target.value as PresenceFilter)}><option value="true">Да</option><option value="false">Нет</option><option value="">Все</option></select></label></div><div className="filter-groups"><MultiFilter title="Тип цены" values={props.options.price_types} selected={props.priceType} onChange={props.onPriceType} /><MultiFilter title="Вид покупателя" values={props.options.buyer_types} selected={props.buyerType} onChange={props.onBuyerType} /><MultiFilter title="Вид контрагента" values={props.options.counterparty_types} selected={props.counterpartyType} onChange={props.onCounterpartyType} /><MultiFilter title="Менеджер" values={props.options.managers} selected={props.manager} onChange={props.onManager} searchable /></div><footer className="filter-actions"><button className="tonal" type="button" onClick={props.onReset}>Сбросить</button><button className="primary-action" type="button" onClick={props.onClose}>Показать результаты</button></footer></section></div>;
}
function Settings({ active, onChange, onUpload, onDeleteAllClients, notice, uploading, logs, logsLoading, logSource, onRefreshLogs, onShowAllLogs, onOpenFtpLogs, onDeleteLogs }: { active: HelpTab; onChange: (tab: HelpTab) => void; onUpload: () => void; onDeleteAllClients: () => void; notice: string; uploading: boolean; logs: LogEntry[]; logsLoading: boolean; logSource: string; onRefreshLogs: () => void; onShowAllLogs: () => void; onOpenFtpLogs: () => void; onDeleteLogs: () => void }) {
  const updateCommand = '/var/www/html/vr/clients/update.sh';
  const copyUpdateCommand = async () => navigator.clipboard.writeText(updateCommand);
  return <section className="help card"><div className="settings-heading"><h2>Настройки</h2><div className="settings-actions"><button className="danger-action" type="button" disabled={uploading} onClick={onDeleteAllClients}>Удалить все строки</button><button className="primary-action" disabled={uploading} onClick={onUpload}>{uploading ? 'Загрузка…' : 'Загрузить XLS'}</button></div></div>{notice && <div className="notice" role="status">{notice}</div>}<div className="subtabs"><button className={active === 'features' ? 'selected' : ''} onClick={() => onChange('features')}>Описание и возможности</button><button className={active === 'manual' ? 'selected' : ''} onClick={() => onChange('manual')}>Инструкция для пользователя</button><button className={active === 'autoload' ? 'selected' : ''} onClick={() => onChange('autoload')}>Автозагрузка</button><button className={active === 'journal' ? 'selected' : ''} onClick={() => onChange('journal')}>Журнал загрузки</button></div>{active !== 'journal' && active !== 'autoload' && <div className="copy-row"><textarea readOnly value={updateCommand} aria-label="Команда обновления проекта" /><button title="Копировать в буфер обмена" onClick={copyUpdateCommand}>📋</button></div>}{active === 'features' ? <div><h3>Описание и возможности</h3><ul><li>Импорт клиентов из файлов Excel `.xls` и `.xlsx`.</li><li>Поиск и фильтрация реестра клиентов.</li><li>Ручная и автоматическая загрузка XLS по FTP.</li></ul></div> : active === 'manual' ? <div><h3>Инструкция для пользователя</h3><ol><li>Для ручной загрузки нажмите «Загрузить XLS».</li><li>Для настройки FTP откройте раздел «Автозагрузка».</li><li>Кликните по строке реестра, чтобы открыть карточку клиента.</li></ol></div> : active === 'autoload' ? <FtpSettingsPanel onOpenLogs={onOpenFtpLogs} /> : <UploadJournal logs={logs} loading={logsLoading} source={logSource} onRefresh={onRefreshLogs} onShowAll={onShowAllLogs} onDelete={onDeleteLogs} />}</section>;
}

function FtpSettingsPanel({ onOpenLogs }: { onOpenLogs: () => void }) {
  const [settings, setSettings] = useState<any>(null);
  const [status, setStatus] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const load = async () => { const [nextSettings, nextStatus] = await Promise.all([api('/ftp/settings'), api('/ftp/status')]); setSettings(nextSettings); setStatus(nextStatus); };
  useEffect(() => { load().catch(error => setMessage(String(error))); const timer = window.setInterval(() => api('/ftp/status').then(setStatus), 2000); return () => window.clearInterval(timer); }, []);
  if (!settings) return <p>Загрузка настроек FTP…</p>;
  const update = (key: string, value: string | number) => setSettings((previous: any) => ({ ...previous, [key]: value }));
  const save = async () => { setBusy(true); try { setSettings(await api('/ftp/settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(settings) })); setMessage('Настройки сохранены.'); } catch (error) { setMessage(String(error)); } finally { setBusy(false); } };
  const test = async () => { setBusy(true); setMessage('Проверка подключения…'); try { const result = await api('/ftp/test', { method: 'POST' }); setMessage(`Подключение установлено. Каталог: ${result.directory}. Найдено XLS: ${result.found_files}.`); await load(); } catch (error) { setMessage(String(error)); } finally { setBusy(false); } };
  const run = async () => { setBusy(true); setMessage('Проверка подключения…'); try { await api('/ftp/run', { method: 'POST' }); let current = await api('/ftp/status'); while (current.running || current.stage === 'Ожидание') { setStatus(current); setMessage(current.stage); await new Promise(resolve => window.setTimeout(resolve, 1500)); current = await api('/ftp/status'); } setStatus(current); setMessage('Готово.'); } catch (error) { setMessage(String(error)); } finally { setBusy(false); } };
  const statusLabel = status?.connection_status === 'connected' ? '🟢 Подключение установлено' : status?.connection_status === 'checking' ? '🟡 Выполняется проверка...' : status?.connection_status === 'auth_error' ? '🔴 Ошибка авторизации' : status?.connection_status === 'unavailable' ? '🔴 FTP недоступен' : '🔴 Нет соединения';
  return <section className="ftp-panel"><div className="ftp-status"><h3>{statusLabel}</h3><p>{status?.stage}</p>{status?.last_successful_check && <p>Последняя успешная проверка: {formatMoscowTime(status.last_successful_check)}</p>}<p>Следующая автоматическая проверка: {formatMoscowTime(status?.next_run)}</p><p>Найдено XLS-файлов: {status?.found_files ?? 0}</p></div>{message && <div className="notice">{message}</div>}<h3>Настройки FTP</h3><div className="ftp-form"><label>Хост<input value={settings.host} onChange={event => update('host', event.target.value)} /></label><label>Порт<input type="number" value={settings.port} onChange={event => update('port', Number(event.target.value))} /></label><label>Пользователь<input value={settings.user} onChange={event => update('user', event.target.value)} /></label><label>Пароль<input type="password" value={settings.password} placeholder={settings.password_configured ? 'Пароль сохранён' : 'Введите пароль'} onChange={event => update('password', event.target.value)} /></label><label>Каталог<input value={settings.directory} onChange={event => update('directory', event.target.value)} /></label><label>Время ежедневного запуска<input type="time" value={settings.run_time} onChange={event => update('run_time', event.target.value)} /></label><label>Интервал повторов, минут<input type="number" value={settings.retry_minutes} onChange={event => update('retry_minutes', Number(event.target.value))} /></label><label>Максимум попыток<input type="number" value={settings.max_attempts} onChange={event => update('max_attempts', Number(event.target.value))} /></label></div><div className="ftp-actions"><button className="tonal" disabled={busy || status?.running} onClick={save}>Сохранить</button><button className="tonal" disabled={busy || status?.running} onClick={test}>Проверить подключение</button><button className="primary-action" disabled={busy || status?.running} onClick={run}>Тест автозагрузки</button><button className="tonal" onClick={onOpenLogs}>Открыть журнал загрузки</button></div><section className="ftp-stat"><h3>Последняя загрузка</h3><p>Дата успешной загрузки: {formatMoscowTime(status?.last_successful_import)}</p><p>Обработано файлов: {status?.processed_files ?? 0}</p><p>Успешно: {status?.successful_files ?? 0}</p><p>С ошибкой: {status?.failed_files ?? 0}</p><p>Следующий запуск: {formatMoscowTime(status?.next_run)}</p></section></section>;
}

function UploadJournal({ logs, loading, source, onRefresh, onShowAll, onDelete }: { logs: LogEntry[]; loading: boolean; source: string; onRefresh: () => void; onShowAll: () => void; onDelete: () => void }) {
  return <section className="upload-journal"><div className="journal-heading"><div><h3>Журнал загрузки{source ? ` · ${source}` : ''}</h3><p>Последние 100 событий. Время указано по Москве (UTC+3).</p></div><div className="journal-actions">{source && <button className="tonal" onClick={onShowAll}>Показать все</button>}<button className="tonal" disabled={loading} onClick={onRefresh}>{loading ? 'Обновление…' : 'Обновить'}</button><button className="danger-action" disabled={loading} onClick={onDelete}>Удалить все события</button></div></div>{!loading && logs.length === 0 ? <p className="empty-state">Событий пока нет.</p> : <div className="journal-table"><table><thead><tr><th>Дата (МСК)</th><th>Источник</th><th>Файл</th><th>Итог загрузки</th></tr></thead><tbody>{logs.map(entry => <tr key={entry.id} className={`log-${entry.level}`}><td>{formatMoscowTime(entry.created_at)}</td><td><span className="log-level">{entry.source}</span></td><td>{entry.process || '—'}</td><td>{entry.message || 'Описание отсутствует'}</td></tr>)}</tbody></table></div>}</section>;
}
function ClientCard({ c }: { c: any }) { const phones = c.phones || []; return <div className="card"><h2>{c.name}</h2><Block title="Информация о записи" rows={[["Дата загрузки", c.first_import_at ? formatMoscowTime(c.first_import_at) : null], ["Дата обновления", c.updated_at ? formatMoscowTime(c.updated_at) : null]]} /><Block title="Все поля XLS" rows={[["Наименование", c.name], ["Тип цены", c.price_type], ["Менеджер", c.manager], ["Дата рождения", c.birth_date], ["Email", c.emails?.join(', ')], ["Телефоны прочие", c.raw_common_phones || phones.filter((p: any) => p.type === 'common').map((p: any) => p.phone).join(', ')], ["Места торговли", c.trade_places?.join(', ')], ["Телефоны для СМС и рассылки", c.raw_sms_phones || phones.filter((p: any) => p.type === 'sms').map((p: any) => p.phone).join(', ')], ["Руководитель", c.director], ["Фирма", c.company], ["Контактное лицо", c.contact_person], ["Источник клиента", c.client_source], ["Дата последней покупки", c.last_purchase_date], ["Вид покупателя", c.buyer_type], ["Вид контрагента", c.counterparty_type]]} /></div>; }
function Block({ title, rows }: any) { const filledRows = rows.filter((row: any) => Array.isArray(row[1]) ? row[1].length > 0 : row[1] !== null && row[1] !== undefined && String(row[1]).trim() !== ''); return <section><h3>{title}</h3>{filledRows.map((row: any) => <p key={row[0]}><b>{row[0]}:</b> {row[1]}</p>)}</section>; }
createRoot(document.getElementById('root')!).render(<App />);
