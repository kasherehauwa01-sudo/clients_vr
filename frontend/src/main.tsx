import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

type Client = { id: number; name: string; company?: string; manager?: string; phone?: string; email?: string; trade_place?: string; birth_date?: string; status: ClientStatus };
type ClientStatus = 'active' | 'archived' | 'out_of_stock';
type MainTab = 'registry' | 'logs' | 'help';
type HelpTab = 'features' | 'manual';
type ProcessLog = { id: string; created_at?: string; source: string; level: string; process?: string; row_number?: number; message: string };

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
  const [page, setPage] = useState(1);
  const [detail, setDetail] = useState<any>(null);
  const [notice, setNotice] = useState('');
  const [importLog, setImportLog] = useState<string[]>([]);
  const [processLogs, setProcessLogs] = useState<ProcessLog[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const query = useMemo(() => new URLSearchParams({ page: String(page), page_size: '50', search: q }).toString(), [q, page]);
  const load = () => api(`/clients?${query}`).then(d => { setClients(d.items); setTotal(d.total); });

  useEffect(() => { if (activeTab === 'registry') load(); }, [query, activeTab]);

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
      <section className="toolbar"><input placeholder="Поиск по клиентам, email, телефонам, фирме..." value={q} onChange={e => { setQ(e.target.value); setPage(1); }} /><a className="button tonal" href={`${API_BASE_URL}/clients-export.xlsx`}>Скачать</a></section>
      {notice && <div className="notice">{notice}</div>}
      {importLog.length > 0 && <details className="import-log" open><summary>Журнал импорта</summary><pre>{importLog.join('\n')}</pre></details>}
      <div className="grid"><section className="table"><table><thead><tr><th>Наименование</th><th>Фирма</th><th>Менеджер</th><th>Телефон</th><th>Email</th><th>Место торговли</th><th>Дата рождения</th></tr></thead><tbody>{clients.map(c => <tr key={c.id} className={c.status === 'out_of_stock' ? 'muted-row' : ''} onClick={() => api(`/clients/${c.id}`).then(setDetail)}><td><b>{c.name}</b></td><td>{c.company}</td><td>{c.manager}</td><td>{c.phone}</td><td>{c.email}</td><td>{c.trade_place}</td><td>{c.birth_date}</td></tr>)}</tbody></table><footer><button disabled={page === 1} onClick={() => setPage(page - 1)}>Назад</button><span>{page} / {Math.ceil(total / 50) || 1} · {total} записей</span><button disabled={page * 50 >= total} onClick={() => setPage(page + 1)}>Вперед</button></footer></section>
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
function ClientCard({ c }: { c: any }) { return <div className="card"><h2>{c.name}</h2><Block title="Основная информация" rows={[["Фирма", c.company], ["Тип цены", c.price_type], ["Менеджер", c.manager], ["Статус", STATUS_LABELS[c.status as ClientStatus] || c.status]]} /><Block title="Контакты" rows={[["Контактное лицо", c.contact_person], ["Руководитель", c.director], ["Email", c.emails?.join(', ')], ["Все телефоны", c.phones?.map((p: any) => `${p.phone} (${p.type})`).join(', ')]]} /><Block title="Дополнительно" rows={[["Дата рождения", c.birth_date], ["Места торговли", c.trade_places?.join(', ')]]} /><Block title="История" rows={[["Первый импорт", c.first_import_at?.slice(0, 10)], ["Последнее обновление", c.updated_at?.slice(0, 10)], ["Последний импорт", c.last_import_at?.slice(0, 10)], ["Файл", c.last_import_file]]} /></div>; }
function Block({ title, rows }: any) { return <section><h3>{title}</h3>{rows.map((r: any) => <p key={r[0]}><b>{r[0]}:</b> {r[1] || '—'}</p>)}</section>; }
createRoot(document.getElementById('root')!).render(<App />);
