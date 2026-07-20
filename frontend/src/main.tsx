import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

type Client = { id: number; name: string; company?: string; manager?: string; phone?: string; email?: string; trade_place?: string; birth_date?: string; status: ClientStatus };
type ClientStatus = 'active' | 'archived' | 'out_of_stock';
type MainTab = 'registry' | 'logs' | 'help';
type HelpTab = 'features' | 'manual';
type ProcessLog = { id: string; created_at?: string; source: string; level: string; process?: string; row_number?: number; message: string };
type FilterOptions = { managers: string[]; price_types: string[]; buyer_types: string[]; counterparty_types: string[] };

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
  if (!response.ok) throw new Error(await response.text());
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
  const [detail, setDetail] = useState<any>(null);
  const [selectedClientId, setSelectedClientId] = useState<number | null>(null);
  const [notice, setNotice] = useState('');
  const [importLog, setImportLog] = useState<string[]>([]);
  const [processLogs, setProcessLogs] = useState<ProcessLog[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const query = useMemo(() => {
    const params = new URLSearchParams({ page: String(page), page_size: '50' });
    if (q) params.set('search', q);
    if (manager) params.set('manager', manager);
    if (priceType) params.set('price_type', priceType);
    if (hasPhone) params.set('has_phone', hasPhone);
    if (hasEmail) params.set('has_email', hasEmail);
    if (buyerType) params.set('buyer_type', buyerType);
    if (counterpartyType) params.set('counterparty_type', counterpartyType);
    return params.toString();
  }, [q, page, manager, priceType, hasPhone, hasEmail, buyerType, counterpartyType]);
  const load = () => api(`/clients?${query}`).then(d => { setClients(d.items); setTotal(d.total); });
  const resetFilters = () => { setQ(''); setPriceType(''); setBuyerType(''); setCounterpartyType(''); setManager(''); setHasPhone(''); setHasEmail(''); setPage(1); };

  useEffect(() => { if (activeTab === 'registry') load(); }, [query, activeTab]);
  useEffect(() => { api('/clients-filter-options').then(setFilterOptions); }, []);

  const loadLogs = async () => {
    setLogsLoading(true);
    try {
      setProcessLogs(await api('/logs'));
    } finally {
      setLogsLoading(false);
    }
  };

  useEffect(() => { if (activeTab === 'logs') loadLogs(); }, [activeTab]);

  const upload = async (files: FileList | null) => {
    if (!files?.length) return;
    const fd = new FormData();
    [...files].forEach(f => fd.append('files', f));
    setNotice(`Загрузка файлов: ${files.length}`);
    setImportLog([]);
    const r = await api('/imports', { method: 'POST', body: fd });
    setNotice(`${r.message}. Всего строк: ${r.rows}. Прочитано: ${r.read}. Добавлено: ${r.added}. Обновлено: ${r.updated}. Пропущено: ${r.skipped}. Ошибок: ${r.errors}`);
    setImportLog(r.logs || []);
    if (fileInputRef.current) fileInputRef.current.value = '';
    load();
  };

  return <main>
    <header className="topbar">
      <div>
        <p className="eyebrow">Client registry</p>
        <h1>База клиентов</h1>
        <p>Быстрый поиск, импорт Excel и карточки клиентов</p>
      </div>
      {activeTab === 'registry' && <div className="header-actions">
        <input ref={fileInputRef} className="hidden-file" type="file" multiple accept=".xls,.xlsx" onChange={e => upload(e.target.files)} />
        <button className="primary-action" onClick={() => fileInputRef.current?.click()}>Загрузить</button>
      </div>}
    </header>
    <nav className="tabs"><button className={activeTab === 'registry' ? 'selected' : ''} onClick={() => setActiveTab('registry')}>Реестр</button><button className={activeTab === 'logs' ? 'selected' : ''} onClick={() => setActiveTab('logs')}>Логи</button><button className={activeTab === 'help' ? 'selected' : ''} onClick={() => setActiveTab('help')}>Помощь</button></nav>
    {activeTab === 'help' ? <Help active={helpTab} onChange={setHelpTab} /> : activeTab === 'logs' ? <Logs items={processLogs} loading={logsLoading} onRefresh={loadLogs} /> : <>
      <section className="toolbar filters"><input className="search" placeholder="Поиск по клиентам, email, телефонам, фирме..." value={q} onChange={e => { setQ(e.target.value); setPage(1); }} /><select aria-label="Тип цены" value={priceType} onChange={e => { setPriceType(e.target.value); setPage(1); }}><option value="">Все типы цены</option>{filterOptions.price_types.map(value => <option key={value} value={value}>{value}</option>)}</select><select aria-label="Вид покупателя" value={buyerType} onChange={e => { setBuyerType(e.target.value); setPage(1); }}><option value="">Все виды покупателей</option>{filterOptions.buyer_types.map(value => <option key={value} value={value}>{value}</option>)}</select><select aria-label="Вид контрагента" value={counterpartyType} onChange={e => { setCounterpartyType(e.target.value); setPage(1); }}><option value="">Все виды контрагентов</option>{filterOptions.counterparty_types.map(value => <option key={value} value={value}>{value}</option>)}</select><select aria-label="Менеджер" value={manager} onChange={e => { setManager(e.target.value); setPage(1); }}><option value="">Все менеджеры</option>{filterOptions.managers.map(value => <option key={value} value={value}>{value}</option>)}</select><select aria-label="Наличие телефона" value={hasPhone} onChange={e => { setHasPhone(e.target.value); setPage(1); }}><option value="">Телефон: все</option><option value="true">Телефон: есть</option><option value="false">Телефон: нет</option></select><select aria-label="Наличие Email" value={hasEmail} onChange={e => { setHasEmail(e.target.value); setPage(1); }}><option value="">Email: все</option><option value="true">Email: есть</option><option value="false">Email: нет</option></select><button className="tonal" type="button" onClick={resetFilters}>Сбросить фильтры</button><a className="button tonal" href={`${API_BASE_URL}/clients-export.xlsx`}>Скачать</a></section>
      {notice && <div className="notice">{notice}</div>}
      {importLog.length > 0 && <details className="import-log" open><summary>Журнал импорта</summary><pre>{importLog.join('\n')}</pre></details>}
      <div className="grid"><section className="table"><table><thead><tr><th>Наименование</th><th>Фирма</th><th>Менеджер</th><th>Телефоны</th></tr></thead><tbody>{clients.map(c => <tr key={c.id} className={[c.status === 'out_of_stock' ? 'muted-row' : '', selectedClientId === c.id ? 'selected-row' : ''].filter(Boolean).join(' ')} aria-selected={selectedClientId === c.id} onClick={() => { setSelectedClientId(c.id); api(`/clients/${c.id}`).then(setDetail); }}><td><b>{c.name}</b></td><td>{c.company}</td><td>{c.manager}</td><td>{c.phone}</td></tr>)}</tbody></table><footer><button disabled={page === 1} onClick={() => setPage(page - 1)}>Назад</button><span>{page} / {Math.ceil(total / 50) || 1} · {total} записей</span><button disabled={page * 50 >= total} onClick={() => setPage(page + 1)}>Вперед</button></footer></section>
        <aside>{detail ? <ClientCard c={detail} /> : <div className="card empty-state"><h2>Карточка клиента</h2><p>Выберите строку в реестре, чтобы посмотреть подробную информацию.</p></div>}</aside></div></>}
  </main>;
}
function Logs({ items, loading, onRefresh }: { items: ProcessLog[]; loading: boolean; onRefresh: () => void }) {
  return <section className="card logs-page"><div className="logs-header"><div><h2>Логи</h2><p>События импорта, предупреждения, ошибки и операции пользователей с сервера.</p></div><button className="tonal" onClick={onRefresh} disabled={loading}>{loading ? 'Загрузка...' : 'Обновить'}</button></div><div className="logs-list">{items.length === 0 ? <p>Логов пока нет.</p> : items.map(item => <article className={`log-item ${item.level}`} key={item.id}><div className="log-meta"><span>{item.created_at?.slice(0, 19).replace('T', ' ') || '—'}</span><span>{item.source}</span><span>{item.level}</span>{item.row_number ? <span>Строка {item.row_number}</span> : null}</div><h3>{item.process || 'Процесс'}</h3><p>{item.message || '—'}</p></article>)}</div></section>;
}
function Help({ active, onChange }: { active: HelpTab; onChange: (tab: HelpTab) => void }) {
  const updateCommand = '/var/www/html/vr/clients/update.sh';
  const copyUpdateCommand = async () => {
    await navigator.clipboard.writeText(updateCommand);
  };
  return <section className="help card"><h2>Помощь</h2><div className="subtabs"><button className={active === 'features' ? 'selected' : ''} onClick={() => onChange('features')}>Описание и возможности</button><button className={active === 'manual' ? 'selected' : ''} onClick={() => onChange('manual')}>Инструкция для пользователя</button></div><div className="copy-row"><textarea readOnly value={updateCommand} aria-label="Команда обновления проекта" /><button title="Копировать в буфер обмена" onClick={copyUpdateCommand}>📋</button></div>{active === 'features' ? <div><h3>Описание и возможности</h3><ul><li>Импорт клиентов из файлов Excel `.xls` и `.xlsx`.</li><li>Поиск по наименованию, фирме, контактам, email, телефонам и местам торговли.</li><li>Экспорт списка клиентов в Excel.</li><li>Статус «Нет в наличии» всегда отображается в конце реестра.</li></ul></div> : <div><h3>Инструкция для пользователя</h3><ol><li>Нажмите кнопку «Загрузить» в правом верхнем углу.</li><li>Выберите один или несколько файлов `.xls` или `.xlsx`.</li><li>Дождитесь отчета о добавленных, обновленных, пропущенных строках и ошибках.</li><li>Используйте поиск для быстрого отбора клиентов.</li><li>Кликните по строке, чтобы открыть карточку клиента.</li></ol></div>}</section>;
}
function ClientCard({ c }: { c: any }) { const phones = c.phones || []; return <div className="card"><h2>{c.name}</h2><Block title="Все поля XLS" rows={[["Наименование", c.name], ["Тип цены", c.price_type], ["Менеджер", c.manager], ["Дата рождения", c.birth_date], ["Email", c.emails?.join(', ')], ["Телефоны прочие", phones.filter((p: any) => p.type === 'common').map((p: any) => p.phone).join(', ')], ["Места торговли", c.trade_places?.join(', ')], ["Телефоны для СМС и рассылки", phones.filter((p: any) => p.type === 'sms').map((p: any) => p.phone).join(', ')], ["Руководитель", c.director], ["Фирма", c.company], ["Контактное лицо", c.contact_person], ["Источник клиента", c.client_source], ["Дата последней покупки", c.last_purchase_date], ["Вид покупателя", c.buyer_type], ["Вид контрагента", c.counterparty_type]]} /></div>; }
function Block({ title, rows }: any) { return <section><h3>{title}</h3>{rows.map((r: any) => <p key={r[0]}><b>{r[0]}:</b> {r[1] || '—'}</p>)}</section>; }
createRoot(document.getElementById('root')!).render(<App />);
