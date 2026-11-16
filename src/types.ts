export type Domain = {
  id: number
  name: string
  is_ssl: boolean
  state: string
}

export type NamedEntity = {
  id: number
  name: string
}

export type Offer = NamedEntity & {
  country: string[]
  state: string
}

export type Catalog = {
  domains: Domain[]
  groups: NamedEntity[]
  traffic_sources: NamedEntity[]
  offers: Offer[]
}

export type CampaignListItem = {
  id: number
  name: string
  alias: string
  state: string
  domain_id: number | null
  group_id: number | null
  traffic_source_id: number | null
  created_here: boolean
}

export type OfferRow = {
  relation_id: number | null
  offer_id: number
  name: string
  share: number
  state: string
  pinned: boolean
  country: string[]
}

export type Flow = {
  id: number
  name: string
  flow_schema: string
  action_type: string
  action_payload: string
  countries: string[]
  dirty: boolean
  offers: OfferRow[]
}

export type CampaignDetail = {
  id: number
  name: string
  alias: string
  state: string
  domain_id: number | null
  group_id: number | null
  traffic_source_id: number | null
  tracking_url: string | null
  admin_url: string | null
  google_flow: Flow | null
  offer_flow: Flow | null
}
