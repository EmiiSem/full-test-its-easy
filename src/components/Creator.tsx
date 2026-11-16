import { useMemo, useState, type FormEvent } from "react"
import { api } from "../api"
import type { Catalog, CampaignDetail } from "../types"

type Props = {
  catalog: Catalog
  onCreated: (campaign: CampaignDetail) => void
}

const PREFIX = "test_plaskin_"

export function Creator({ catalog, onCreated }: Props) {
  const defaultDomain = catalog.domains[0]?.id ?? 0
  const defaultGroup =
    catalog.groups.find((group) => group.name === "FORTESTS")?.id ??
    catalog.groups[0]?.id ??
    0
  const defaultSource =
    catalog.traffic_sources.find((source) => source.name === "FORTESTS")?.id ??
    catalog.traffic_sources[0]?.id ??
    0

  const [name, setName] = useState(PREFIX)
  const [geos, setGeos] = useState("AU")
  const [query, setQuery] = useState("")
  const [offerId, setOfferId] = useState<number | null>(null)
  const [domainId, setDomainId] = useState(defaultDomain)
  const [groupId, setGroupId] = useState(defaultGroup)
  const [sourceId, setSourceId] = useState(defaultSource)
  const [error, setError] = useState("")
  const [pending, setPending] = useState(false)

  const matches = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return catalog.offers.slice(0, 8)
    return catalog.offers
      .filter((offer) => {
        const country = offer.country.join(" ").toLowerCase()
        return (
          offer.name.toLowerCase().includes(needle) ||
          String(offer.id).includes(needle) ||
          country.includes(needle)
        )
      })
      .slice(0, 8)
  }, [catalog.offers, query])

  const selected = catalog.offers.find((offer) => offer.id === offerId) ?? null

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError("")
    if (!offerId) {
      setError("Выберите оффер из списка")
      return
    }
    setPending(true)
    try {
      const created = await api<CampaignDetail>("/api/campaigns", {
        method: "POST",
        body: JSON.stringify({
          name,
          geos,
          offer_id: offerId,
          domain_id: Number(domainId),
          group_id: Number(groupId),
          traffic_source_id: Number(sourceId),
        }),
      })
      onCreated(created)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось создать кампанию")
    } finally {
      setPending(false)
    }
  }

  return (
    <form className="panel" onSubmit={submit}>
      <header className="panel-head">
        <p className="eyebrow">Часть 1</p>
        <h2>Новая кампания</h2>
        <p className="lede">
          Поток для выбранных стран уходит на Google. Остальной трафик попадает на оффер.
          Домен, группа и источник берутся из Keitaro.
        </p>
      </header>

      <label>
        Название
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="test_plaskin_campaign1"
          required
        />
      </label>

      <label>
        Гео
        <input
          value={geos}
          onChange={(event) => setGeos(event.target.value)}
          placeholder="MX, AU, RO"
          required
        />
      </label>

      <div className="field">
        <span>Оффер</span>
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Поиск по названию, ID или стране"
          aria-label="Поиск оффера"
        />
        <ul className="choices">
          {matches.map((offer) => (
            <li key={offer.id}>
              <button
                type="button"
                className={offer.id === offerId ? "choice is-selected" : "choice"}
                onClick={() => {
                  setOfferId(offer.id)
                  setQuery(offer.name)
                }}
              >
                <b>[{offer.id}]</b> {offer.name}
                {offer.country.length > 0 && <small>{offer.country.join(", ")}</small>}
              </button>
            </li>
          ))}
          {matches.length === 0 && <li className="empty">Ничего не найдено</li>}
        </ul>
        {selected && (
          <p className="picked">
            Выбран [{selected.id}] {selected.name}
          </p>
        )}
      </div>

      <div className="grid-3">
        <label>
          Домен
          <select value={domainId} onChange={(event) => setDomainId(Number(event.target.value))}>
            {catalog.domains.map((domain) => (
              <option key={domain.id} value={domain.id}>
                {domain.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Группа
          <select value={groupId} onChange={(event) => setGroupId(Number(event.target.value))}>
            {catalog.groups.map((group) => (
              <option key={group.id} value={group.id}>
                {group.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Источник
          <select value={sourceId} onChange={(event) => setSourceId(Number(event.target.value))}>
            {catalog.traffic_sources.map((source) => (
              <option key={source.id} value={source.id}>
                {source.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      {error && <p className="banner">{error}</p>}

      <button className="primary" type="submit" disabled={pending}>
        {pending ? "Создаём…" : "Создать кампанию"}
      </button>
    </form>
  )
}
