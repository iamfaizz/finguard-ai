import React, {useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import {api} from '../api';
import {LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer} from 'recharts';

const money = (v: number | string) =>
    Number(v).toLocaleString('en-IN', {
        style: 'currency', currency: 'INR'
    });

interface Forecast {
    forecast_days: number;
    total_predicted_spending: number;
    dates: string[];
    daily_predicted_spending: number[];
    low_confidence: boolean;
    confidence_note: string;
}

interface Goal {
    id: number;
    name: string;
    target: string;
    saved: string;
    target_date: string | null;
}

interface GoalPlan {
    name: string;
    required_monthly_inr: string;
    progress_pct: number;
    on_track: boolean;
}

export default function Planning() {
    const [name, setName] = useState('');
    const [target, setTarget] = useState('');
    const [saved, setSaved] = useState('0');
    const [date, setDate] = useState('');
    const [editing, setEditing] = useState<number | null>(null);
    const [message, setMessage] = useState('');
    const [busy, setBusy] = useState(false);

    const forecast = useQuery<Forecast>({
        queryKey: ['forecast'],
        queryFn: async () => (await api.get('/forecast')).data,
        retry: false
    });

    const goals = useQuery<Goal[]>({
        queryKey: ['goals'],
        queryFn: async () => (await api.get('/goals')).data
    });

    const plan = useQuery<{goals: GoalPlan[]}>({
        queryKey: ['goal-plan'],
        queryFn: async () =>
            (await api.get('/api/advisor-tools/goal-status')).data,
        retry: false
    });

    function reset() {
        setName('');
        setTarget('');
        setSaved('0');
        setDate('');
        setEditing(null);
    }

    async function save(e: React.FormEvent) {
        e.preventDefault();
        setBusy(true);
        try {
            const body = {
                name, target: Number(target),
                saved: Number(saved), target_date: date
            };
            if (editing !== null)
                await api.put(`/goals/${editing}`, body);
            else
                await api.post('/goals', body);

            reset();
            setMessage('Goal saved successfully');
            await Promise.all([goals.refetch(), plan.refetch()]);
        } catch {
            setMessage('Unable to save goal');
        } finally {
            setBusy(false);
        }
    }

    async function remove(id: number) {
        if (!window.confirm('Delete this goal?')) return;
        try {
            await api.delete(`/goals/${id}`);
            reset();
            setMessage('Goal deleted');
            await Promise.all([goals.refetch(), plan.refetch()]);
        } catch {
            setMessage('Unable to delete goal');
        }
    }

    return <section>
        <article>
            <h2>Spending forecast</h2>
            <button onClick={() => forecast.refetch()}>
                Refresh forecast
            </button>

            {forecast.isLoading && <p>Loading forecast...</p>}
            {forecast.isError &&
                <p>Forecast unavailable. Upload transaction history and retry.</p>}

            {forecast.data && <>
                <h3>{forecast.data.forecast_days}-day estimated spending</h3>
                <strong>{money(forecast.data.total_predicted_spending)}</strong>
                <p>{forecast.data.low_confidence ?
                    'Low confidence' : 'Forecast available'}</p>
                <p>{forecast.data.confidence_note}</p>

                <ResponsiveContainer width="100%" height={240}>
                    <LineChart data={forecast.data.dates.map((date, i) => ({
                        date,
                        amount: forecast.data!.daily_predicted_spending[i]
                    }))}>
                        <XAxis dataKey="date"/>
                        <YAxis/>
                        <Tooltip/>
                        <Line dataKey="amount" stroke="#2563eb"/>
                    </LineChart>
                </ResponsiveContainer>
            </>}
        </article>

        <article>
            <h2>Savings goals</h2>

            <form onSubmit={save}>
                <label>Goal name
                    <input required maxLength={100} value={name}
                        onChange={e => setName(e.target.value)}/>
                </label>
                <label>Target amount
                    <input type="number" required min="0.01"
                        step="0.01" value={target}
                        onChange={e => setTarget(e.target.value)}/>
                </label>
                <label>Saved amount
                    <input type="number" required min="0"
                        step="0.01" value={saved}
                        onChange={e => setSaved(e.target.value)}/>
                </label>
                <label>Target date
                    <input type="date" required value={date}
                        onChange={e => setDate(e.target.value)}/>
                </label>

                <button disabled={busy}>
                    {editing === null ? 'Create goal' : 'Update goal'}
                </button>

                {editing !== null &&
                    <button type="button" onClick={reset}>Cancel</button>}
            </form>

            <p aria-live="polite">{message}</p>

            {goals.isLoading && <p>Loading goals...</p>}
            {goals.isError && <p>Unable to load goals.</p>}

            {goals.data?.map(g => <div key={g.id}>
                <h3>{g.name}</h3>
                <p>{money(g.saved)} / {money(g.target)}</p>
                <p>Target date: {g.target_date || 'Not set'}</p>

                <button onClick={() => {
                    setEditing(g.id);
                    setName(g.name);
                    setTarget(g.target);
                    setSaved(g.saved);
                    setDate(g.target_date || '');
                }}>Edit goal</button>

                <button onClick={() => remove(g.id)}>Delete goal</button>
            </div>)}

            <h3>Goal planning</h3>
            {plan.isError && <p>Goal planning unavailable.</p>}

            {plan.data?.goals.map((g, i) => <div key={i}>
                <strong>{g.name}</strong>
                <p>Monthly requirement: {money(g.required_monthly_inr)}</p>
                <p>Progress: {g.progress_pct}%</p>
                <p>{g.on_track ? 'On track' : 'Needs attention'}</p>
            </div>)}
        </article>
    </section>;
}
