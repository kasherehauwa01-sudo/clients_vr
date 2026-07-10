import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

type Client = { id: number; name: string; company?: string; manager?: string; phone?: string; email?: string; trade_place?: string; birth_date?: string; last_import_at?: string; status: ClientStatus };
type ClientStatus = 'active' | 'archived' | 'out_of_stock';
type MainTab = 'registry' | 'help';
type HelpTab = 'features' | 'manual';

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
  const [clients, setClients] = useState<Client[]>([]), [total, setTotal] = useState(0), [q, setQ] = useState(''), [page, setPage] = useState(1), [selected, setSelected] = useState<number[]>([]), [detail, setDetail] = useState<any>(null), [imports, setImports] = useState<any[]>([]), [notice, setNotice] = useState(''), [drag, setDrag] = useState(false);
  const query = useMemo(() => new URLSearchParams({ page: String(page), page_size: '50', search: q }).toString(), [q, page]);
  const load = () => api(`/clients?${query}`).then(d => { setClients(d.items); setTotal(d.total); });
  useEffect(() => { load(); api('/imports').then(setImports); }, [query]);
  const upload = async (files: FileList | null) => { if (!files?.length) return; const fd = new FormData(); [...files].forEach(f => fd.append('files', f)); setNotice(`Загрузка файлов: ${files.length}`); const r = await api('/imports', { method: 'POST', body: fd }); setNotice(`${r.message}. Добавлено: ${r.added}. Обновлено: ${r.updated}. Пропущено: ${r.skipped}. Ошибок: ${r.errors}`); load(); api('/imports').then(setImports); };
  const bulk = async (payload: any) => { await api('/clients/bulk', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ids: selected, ...payload }) }); setSelected([]); load(); setNotice('Операция выполнена'); };
  return <main>
    <header><h1>База клиентов</h1><p>Поиск, импорт Excel, журнал операций и массовые действия</p></header>
    <nav className="tabs"><button className={activeTab === 'registry' ? 'selected' : ''} onClick={() => setActiveTab('registry')}>Реестр</button><button className={activeTab === 'help' ? 'selected' : ''} onClick={() => setActiveTab('help')}>Помощь</button></nav>
    {activeTab === 'help' ? <Help active={helpTab} onChange={setHelpTab} /> : <>
      <section className="toolbar"><input placeholder="Мгновенный поиск по клиентам, email, телефонам..." value={q} onChange={e => { setQ(e.target.value); setPage(1); }} /><a className="button" href={`${API_BASE_URL}/clients-export.xlsx`}>⬇️ Экспорт</a></section>
      <section className={`drop ${drag ? 'active' : ''}`} onDragOver={e => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={e => { e.preventDefault(); setDrag(false); upload(e.dataTransfer.files); }}>⬆️ <b>Импорт .xls/.xlsx</b><span>Перетащите файлы сюда или выберите несколько файлов</span><input type="file" multiple accept=".xls,.xlsx" onChange={e => upload(e.target.files)} /></section>{notice && <div className="notice">{notice}</div>}
      <section className="bulk"><span>Выбрано: {selected.length}</span><button disabled={!selected.length} onClick={() => bulk({ status: 'archived' })}>📦 Архивировать</button><button disabled={!selected.length} onClick={() => bulk({ status: 'out_of_stock' })}>🚫 Нет в наличии</button><button disabled={!selected.length} onClick={() => bulk({ manager: prompt('Новый менеджер') })}>Сменить менеджера</button><button disabled={!selected.length} onClick={() => bulk({ price_type: prompt('Новый тип цены') })}>Сменить тип цены</button><button disabled={!selected.length} onClick={async () => { await api(`/clients?ids=${selected.join(',')}`, { method: 'DELETE' }); setSelected([]); load(); }}>🗑️ Удалить</button></section>
      <div className="grid"><section className="table"><table><thead><tr><th></th><th>Наименование</th><th>Фирма</th><th>Менеджер</th><th>Телефон</th><th>Email</th><th>Место торговли</th><th>Дата рождения</th><th>Последний импорт</th><th>Статус</th></tr></thead><tbody>{clients.map(c => <tr key={c.id} className={c.status === 'out_of_stock' ? 'muted-row' : ''} onClick={() => api(`/clients/${c.id}`).then(setDetail)}><td onClick={e => e.stopPropagation()}><input type="checkbox" checked={selected.includes(c.id)} onChange={e => setSelected(e.target.checked ? [...selected, c.id] : selected.filter(id => id !== c.id))} /></td><td>{c.name}</td><td>{c.company}</td><td>{c.manager}</td><td>{c.phone}</td><td>{c.email}</td><td>{c.trade_place}</td><td>{c.birth_date}</td><td>{c.last_import_at?.slice(0, 10)}</td><td><span className={`status ${c.status}`}>{STATUS_LABELS[c.status] || c.status}</span></td></tr>)}</tbody></table><footer><button disabled={page === 1} onClick={() => setPage(page - 1)}>Назад</button><span>{page} / {Math.ceil(total / 50) || 1} · {total} записей</span><button disabled={page * 50 >= total} onClick={() => setPage(page + 1)}>Вперед</button></footer></section>
        <aside>{detail ? <ClientCard c={detail} /> : <ImportHistory imports={imports} />}</aside></div></>}
  </main>;
}
function Help({ active, onChange }: { active: HelpTab; onChange: (tab: HelpTab) => void }) {
  const updateCommand = 'cd /var/www/html/vr/clients\n\ngit pull';
  const copyUpdateCommand = async () => {
    await navigator.clipboard.writeText(updateCommand);
  };
  return <section className="help card"><h2>Помощь</h2><div className="subtabs"><button className={active === 'features' ? 'selected' : ''} onClick={() => onChange('features')}>Описание и возможности</button><button className={active === 'manual' ? 'selected' : ''} onClick={() => onChange('manual')}>Инструкция для пользователя</button></div><div className="copy-row"><textarea readOnly value={updateCommand} aria-label="Команда обновления проекта" /><button title="Копировать в буфер обмена" onClick={copyUpdateCommand}>📋</button></div>{active === 'features' ? <div><h3>Описание и возможности</h3><ul><li>Импорт клиентов из файлов Excel `.xls` и `.xlsx`.</li><li>Поиск по наименованию, фирме, контактам, email, телефонам и местам торговли.</li><li>Фильтрация, сортировка, экспорт в Excel и массовые операции.</li><li>Статус «Нет в наличии» всегда отображается в конце реестра.</li></ul></div> : <div><h3>Инструкция для пользователя</h3><ol><li>Загрузите один или несколько Excel-файлов через область импорта.</li><li>Проверьте отчет импорта и журнал ошибок справа.</li><li>Используйте поиск и фильтры для быстрого отбора клиентов.</li><li>Выделите строки галочками, чтобы архивировать, удалить или установить статус «Нет в наличии».</li><li>Кликните по строке, чтобы открыть карточку клиента.</li></ol></div>}</section>;
}
function ClientCard({ c }: { c: any }) { return <div className="card"><h2>{c.name}</h2><Block title="Основная информация" rows={[["Фирма", c.company], ["Тип цены", c.price_type], ["Менеджер", c.manager], ["Статус", STATUS_LABELS[c.status as ClientStatus] || c.status]]} /><Block title="Контакты" rows={[["Контактное лицо", c.contact_person], ["Руководитель", c.director], ["Email", c.emails?.join(', ')], ["Все телефоны", c.phones?.map((p: any) => `${p.phone} (${p.type})`).join(', ')]]} /><Block title="Дополнительно" rows={[["Дата рождения", c.birth_date], ["Места торговли", c.trade_places?.join(', ')]]} /><Block title="История" rows={[["Первый импорт", c.first_import_at?.slice(0, 10)], ["Последнее обновление", c.updated_at?.slice(0, 10)], ["Последний импорт", c.last_import_at?.slice(0, 10)], ["Файл", c.last_import_file]]} /></div>; }
function Block({ title, rows }: any) { return <section><h3>{title}</h3>{rows.map((r: any) => <p key={r[0]}><b>{r[0]}:</b> {r[1] || '—'}</p>)}</section>; }
function ImportHistory({ imports }: any) { return <div className="card"><h2>История импортов</h2>{imports.map((i: any) => <p key={i.id}><b>{i.file_name}</b><br />{i.imported_at?.slice(0, 16)} · строк {i.rows_count} · +{i.added_count} · ↻{i.updated_count} · ошибок {i.error_count}</p>)}</div>; }
createRoot(document.getElementById('root')!).render(<App />);
