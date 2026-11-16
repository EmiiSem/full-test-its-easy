import { useEffect, useMemo, useState } from "react"
import { api } from "../api"
import type { CampaignDetail, CampaignListItem, Catalog } from "../types"

type Props = {
  catalog: Catalog
  campaigns: CampaignListItem[]
  selectedId: number | null
  onSelect: (id: number) => void
  onCampaignsChange: () => void
}

export function Editor({
  catalog,
  campaigns,
  selectedId,
  onSelect,
  onCampaignsChange,
}: Props) {
  const [query, setQuery] = useState("")

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return campaigns
      .filter((campaign) => {
        if (!needle) return true
        return (
          campaign.name.toLowerCase().includes(needle) ||
          String(campaign.id).includes(needle)
        )
      })
      .slice(0, 30)
  }, [campaigns, query])

  return (
    <section className="editor">
      <div className="panel picker">
        <header className="panel-head">
          <p className="eyebrow">Часть 2</p>
          <h2>Кампания</h2>
        </header>
        <label>
          Поиск
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Название или ID"
          />
        </label>
        <ul className="campaign-list">
          {filtered.map((campaign) => (
            <li key={campaign.id}>
              <button
                type="button"
                className={campaign.id === selectedId ? "choice is-selected" : "choice"}
                onClick={() => onSelect(campaign.id)}
              >
                <b>#{campaign.id}</b> {campaign.name}
                {campaign.created_here && <small>создана здесь</small>}
              </button>
            </li>
          ))}
          {filtered.length === 0 && <li className="empty">Кампаний нет</li>}
        </ul>
      </div>

      {selectedId ? (
        <CampaignPanel
          key={selectedId}
          campaignId={selectedId}
          catalog={catalog}
          onCampaignsChange={onCampaignsChange}
        />
      ) : (
        <div className="panel">
          <p className="empty-state">Выберите кампанию слева.</p>
        </div>
      )}
    </section>
  )
}

function CampaignPanel({
  campaignId,
  catalog,
  onCampaignsChange,
}: {
  campaignId: number
  catalog: Catalog
  onCampaignsChange: () => void
}) {
  const [detail, setDetail] = useState<CampaignDetail | null>(null)
  const [offerQuery, setOfferQuery] = useState("")
  const [offerId, setOfferId] = useState<number | null>(null)
  const [error, setError] = useState("")
  const [pending, setPending] = useState(false)

  useEffect(() => {
    let cancelled = false
    api<CampaignDetail>(`/api/campaigns/${campaignId}`)
      .then((next) => {
        if (cancelled) return
        setDetail(next)
      })
      .catch((reason: unknown) => {
        if (cancelled) return
        setError(reason instanceof Error ? reason.message : "Не удалось открыть кампанию")
      })
    return () => {
      cancelled = true
    }
  }, [campaignId])

  const offerMatches = useMemo(() => {
    const taken = new Set(detail?.offer_flow?.offers.map((offer) => offer.offer_id) ?? [])
    const needle = offerQuery.trim().toLowerCase()
    return catalog.offers
      .filter((offer) => !taken.has(offer.id))
      .filter((offer) => {
        if (!needle) return true
        return (
          offer.name.toLowerCase().includes(needle) || String(offer.id).includes(needle)
        )
      })
      .slice(0, 6)
  }, [catalog.offers, detail, offerQuery])

  const activeShares =
    detail?.offer_flow?.offers.filter((offer) => offer.state === "active").map((offer) => offer.share) ??
    []
  const shareSum = activeShares.reduce((total, value) => total + value, 0)

  function apply(next: CampaignDetail) {
    setDetail(next)
    onCampaignsChange()
  }

  async function run(path: string, method: string, body?: unknown) {
    if (!detail) return
    setPending(true)
    setError("")
    try {
      const next = await api<CampaignDetail>(path, {
        method,
        body: body === undefined ? undefined : JSON.stringify(body),
      })
      if (method === "POST" && path.endsWith("/offers")) {
        setOfferId(null)
        setOfferQuery("")
      }
      apply(next)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось обновить поток")
    } finally {
      setPending(false)
    }
  }

  function addOffer() {
    if (!detail || !offerId) return
    return run(`/api/campaigns/${detail.id}/offers`, "POST", { offer_id: offerId })
  }

  return (
    <div className="panel">
      {!detail && !error && <p className="empty-state">Открываем кампанию…</p>}
      {detail && (
        <>
          <header className="panel-head">
            <p className="eyebrow">Потоки</p>
            <h2>{detail.name}</h2>
            <p className="meta">
              #{detail.id} · {detail.alias} · {detail.state}
            </p>
            {detail.tracking_url && (
              <a href={detail.tracking_url} target="_blank" rel="noreferrer">
                {detail.tracking_url}
              </a>
            )}
            <div className="toolbar">
              <button
                type="button"
                className="secondary"
                disabled={pending}
                onClick={() => run(`/api/campaigns/${detail.id}/fetch`, "POST")}
              >
                Обновить из Keitaro
              </button>
              {detail.admin_url && (
                <a className="text-button" href={detail.admin_url} target="_blank" rel="noreferrer">
                  Открыть в Keitaro
                </a>
              )}
              <button
                type="button"
                className="primary"
                disabled={pending || !detail.offer_flow?.dirty}
                onClick={() => run(`/api/campaigns/${detail.id}/push`, "POST")}
              >
                Отправить в Keitaro
              </button>
              <button
                type="button"
                className="ghost"
                disabled={pending || !detail.offer_flow?.dirty}
                onClick={() => run(`/api/campaigns/${detail.id}/cancel`, "POST")}
              >
                Отменить
              </button>
            </div>
          </header>

          <article className="flow">
            <h3>Google</h3>
            {detail.google_flow ? (
              <p>
                Страны <strong>{detail.google_flow.countries.join(", ") || "—"}</strong>
                {" → "}
                {detail.google_flow.action_payload || "https://google.com"}
              </p>
            ) : (
              <p>Поток на Google не найден.</p>
            )}
          </article>

          <article className={detail.offer_flow?.dirty ? "flow is-dirty" : "flow"}>
            <div className="flow-head">
              <h3>Офферы</h3>
              <span className={shareSum === 100 || activeShares.length === 0 ? "sum is-ok" : "sum"}>
                сумма {shareSum}
                {detail.offer_flow?.dirty ? " · не отправлено" : ""}
              </span>
            </div>
            {detail.offer_flow && detail.offer_flow.offers.length > 0 ? (
              <table>
                <thead>
                  <tr>
                    <th>Оффер</th>
                    <th>Доля</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {detail.offer_flow.offers.map((offer) => (
                    <tr key={offer.offer_id} className={offer.state === "removed" ? "is-removed" : undefined}>
                      <td>
                        <b>[{offer.offer_id}]</b> {offer.name}
                        {offer.country.length > 0 && <small>{offer.country.join(", ")}</small>}
                      </td>
                      <td className="share-cell">{offer.share}%</td>
                      <td className="actions">
                        {offer.state === "active" ? (
                          <>
                            <button
                              type="button"
                              className={offer.pinned ? "pin is-on" : "pin"}
                              disabled={pending}
                              onClick={() =>
                                run(`/api/campaigns/${detail.id}/offers/${offer.offer_id}/pin`, "POST")
                              }
                            >
                              {offer.pinned ? "Закреплено" : "Закрепить"}
                            </button>
                            <button
                              type="button"
                              className="ghost"
                              disabled={pending}
                              onClick={() =>
                                run(`/api/campaigns/${detail.id}/offers/${offer.offer_id}`, "DELETE")
                              }
                            >
                              Удалить
                            </button>
                          </>
                        ) : (
                          <button
                            type="button"
                            className="secondary"
                            disabled={pending}
                            onClick={() =>
                              run(
                                `/api/campaigns/${detail.id}/offers/${offer.offer_id}/restore`,
                                "POST",
                              )
                            }
                          >
                            Вернуть
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p>В потоке пока нет офферов.</p>
            )}

            <div className="add-row">
              <input
                value={offerQuery}
                onChange={(event) => setOfferQuery(event.target.value)}
                placeholder="Добавить оффер"
                aria-label="Поиск оффера для добавления"
              />
              <button
                type="button"
                className="primary"
                disabled={pending || !offerId}
                onClick={addOffer}
              >
                Добавить
              </button>
            </div>
            <ul className="choices compact">
              {offerMatches.map((offer) => (
                <li key={offer.id}>
                  <button
                    type="button"
                    className={offer.id === offerId ? "choice is-selected" : "choice"}
                    onClick={() => {
                      setOfferId(offer.id)
                      setOfferQuery(`[${offer.id}] ${offer.name}`)
                    }}
                  >
                    <b>[{offer.id}]</b> {offer.name}
                  </button>
                </li>
              ))}
            </ul>
            <p className="hint">
              Добавление, удаление и возврат меняют только черновик. Закреплённая доля не пересчитывается, остаток делится поровну, лишние проценты достаются последним офферам. В Keitaro уходит только «Отправить».
            </p>
          </article>
        </>
      )}
      {error && <p className="banner">{error}</p>}
    </div>
  )
}

