"""Semantic schema for the energy grid template: the grid, its requests, and the scenarios."""

from relationalai.semantics import Boolean, Float, Integer, Model, String

model = Model("energy_grid_planning")

# Substation
Substation = model.Concept("Substation", identify_by={"id": String})
Substation.name = model.Property(f"{Substation} has {String:name}")
Substation.voltage_kv = model.Property(f"{Substation} has voltage {Float:voltage_kv} kV")
Substation.max_capacity_mw = model.Property(f"{Substation} has max capacity {Float:max_capacity_mw} MW")
Substation.current_load_mw = model.Property(f"{Substation} has current load {Float:current_load_mw} MW")
Substation.latitude = model.Property(f"{Substation} at latitude {Float:latitude}")
Substation.longitude = model.Property(f"{Substation} at longitude {Float:longitude}")

# Generator
Generator = model.Concept("Generator", identify_by={"id": String})
Generator.name = model.Property(f"{Generator} has {String:name}")
Generator.gen_type = model.Property(f"{Generator} has type {String:gen_type}")
Generator.capacity_mw = model.Property(f"{Generator} has capacity {Float:capacity_mw} MW")
Generator.min_output_mw = model.Property(f"{Generator} has minimum output {Float:min_output_mw} MW")
Generator.ramp_rate_mw_per_hr = model.Property(f"{Generator} has ramp rate {Float:ramp_rate_mw_per_hr} MW/hr")
Generator.startup_cost = model.Property(f"{Generator} has startup cost {Float:startup_cost}")
Generator.marginal_cost = model.Property(f"{Generator} has marginal cost {Float:marginal_cost} per MWh")
Generator.min_up_time_hrs = model.Property(f"{Generator} has minimum up time {Integer:min_up_time_hrs} hours")
Generator.min_down_time_hrs = model.Property(f"{Generator} has minimum down time {Integer:min_down_time_hrs} hours")
Generator.emissions_rate = model.Property(f"{Generator} has emissions rate {Float:emissions_rate} tons/MWh")
Generator.is_renewable = model.Property(f"{Generator} is renewable {Boolean:is_renewable}")
Generator.substation = model.Relationship(f"{Generator} connected to {Substation}")

# TransmissionLine
TransmissionLine = model.Concept("TransmissionLine", identify_by={"id": String})
TransmissionLine.from_substation = model.Relationship(
    f"{TransmissionLine} originates at {Substation}", short_name="from_substation")
TransmissionLine.to_substation = model.Relationship(
    f"{TransmissionLine} terminates at {Substation}", short_name="to_substation")
TransmissionLine.capacity_mw = model.Property(f"{TransmissionLine} has capacity {Float:capacity_mw} MW")
TransmissionLine.length_km = model.Property(f"{TransmissionLine} has length {Float:length_km} km")
TransmissionLine.impedance = model.Property(f"{TransmissionLine} has impedance {Float:impedance}")
TransmissionLine.is_active = model.Property(f"{TransmissionLine} is active {Boolean:is_active}")
TransmissionLine.maintenance_priority = model.Property(
    f"{TransmissionLine} has maintenance priority {String:maintenance_priority}")

# LoadZone
LoadZone = model.Concept("LoadZone", identify_by={"id": String})
LoadZone.name = model.Property(f"{LoadZone} has {String:name}")
LoadZone.peak_demand_mw = model.Property(f"{LoadZone} has peak demand {Float:peak_demand_mw} MW")
LoadZone.base_demand_mw = model.Property(f"{LoadZone} has base demand {Float:base_demand_mw} MW")

# DemandPeriod
DemandPeriod = model.Concept("DemandPeriod", identify_by={"id": String})
DemandPeriod.load_zone = model.Relationship(f"{DemandPeriod} in {LoadZone}")
DemandPeriod.period = model.Property(f"{DemandPeriod} at hour {Integer:period}")
DemandPeriod.demand_mw = model.Property(f"{DemandPeriod} has demand {Float:demand_mw} MW")
DemandPeriod.price_per_mwh = model.Property(f"{DemandPeriod} has price {Float:price_per_mwh} per MWh")

# RenewableProfile
RenewableProfile = model.Concept("RenewableProfile", identify_by={"id": String})
RenewableProfile.generator = model.Relationship(f"{RenewableProfile} for {Generator}")
RenewableProfile.period = model.Property(f"{RenewableProfile} at hour {Integer:period}")
RenewableProfile.capacity_factor = model.Property(
    f"{RenewableProfile} has capacity factor {Float:capacity_factor}")

# MaintenanceWindow
MaintenanceWindow = model.Concept("MaintenanceWindow", identify_by={"id": String})
MaintenanceWindow.asset_type = model.Property(f"{MaintenanceWindow} on asset type {String:asset_type}")
MaintenanceWindow.asset_id = model.Property(f"{MaintenanceWindow} on asset {String:asset_id}")
MaintenanceWindow.start_period = model.Property(
    f"{MaintenanceWindow} starts at hour {Integer:start_period}")
MaintenanceWindow.end_period = model.Property(f"{MaintenanceWindow} ends at hour {Integer:end_period}")
MaintenanceWindow.is_planned = model.Property(f"{MaintenanceWindow} is planned {Boolean:is_planned}")

# Customer
Customer = model.Concept("Customer", identify_by={"id": String})
Customer.name = model.Property(f"{Customer} has {String:name}")
Customer.load_zone = model.Relationship(f"{Customer} in {LoadZone}")
Customer.contracted_demand_mw = model.Property(
    f"{Customer} has contracted demand {Float:contracted_demand_mw} MW")
Customer.flexibility_pct = model.Property(f"{Customer} has flexibility {Float:flexibility_pct} percent")
Customer.curtailment_cost_per_mwh = model.Property(
    f"{Customer} has curtailment cost {Float:curtailment_cost_per_mwh} per MWh")

# DataCenterRequest
DataCenterRequest = model.Concept("DataCenterRequest", identify_by={"id": String})
DataCenterRequest.name = model.Property(f"{DataCenterRequest} has {String:name}")
DataCenterRequest.hyperscaler = model.Property(
    f"{DataCenterRequest} from hyperscaler {String:hyperscaler}")
DataCenterRequest.requested_mw = model.Property(
    f"{DataCenterRequest} requesting {Float:requested_mw} MW")
DataCenterRequest.substation = model.Relationship(f"{DataCenterRequest} connected to {Substation}")
DataCenterRequest.annual_revenue_per_mw = model.Property(
    f"{DataCenterRequest} has annual revenue {Float:annual_revenue_per_mw} per MW")
DataCenterRequest.pue = model.Property(
    f"{DataCenterRequest} has power usage effectiveness {Float:pue}")
DataCenterRequest.is_ai_workload = model.Property(
    f"{DataCenterRequest} is AI workload {Boolean:is_ai_workload}")
DataCenterRequest.cooling_type = model.Property(
    f"{DataCenterRequest} has cooling type {String:cooling_type}")
DataCenterRequest.low_carbon_requirement_pct = model.Property(
    f"{DataCenterRequest} has low-carbon requirement {Float:low_carbon_requirement_pct} percent")
DataCenterRequest.queue_position = model.Property(
    f"{DataCenterRequest} has queue position {Integer:queue_position}")
DataCenterRequest.status = model.Property(f"{DataCenterRequest} has status {String:status}")

# SubstationUpgrade
SubstationUpgrade = model.Concept("SubstationUpgrade", identify_by={"id": String})
SubstationUpgrade.substation = model.Relationship(f"{SubstationUpgrade} at {Substation}")
SubstationUpgrade.capacity_increase_mw = model.Property(
    f"{SubstationUpgrade} adds {Float:capacity_increase_mw} MW")
SubstationUpgrade.cost_million = model.Property(
    f"{SubstationUpgrade} costs {Float:cost_million} million dollars")
SubstationUpgrade.lead_time_months = model.Property(
    f"{SubstationUpgrade} has lead time {Integer:lead_time_months} months")
SubstationUpgrade.enables_low_carbon = model.Property(
    f"{SubstationUpgrade} enables low-carbon connection {Boolean:enables_low_carbon}")

# DemandForecast
DemandForecast = model.Concept("DemandForecast", identify_by={"id": String})
DemandForecast.substation = model.Relationship(f"{DemandForecast} for {Substation}")
DemandForecast.forecast_period = model.Property(
    f"{DemandForecast} looking ahead {Integer:forecast_period} months")
DemandForecast.predicted_load_mw = model.Property(
    f"{DemandForecast} predicts {Float:predicted_load_mw} MW load")
DemandForecast.confidence = model.Property(f"{DemandForecast} has confidence {Float:confidence}")
DemandForecast.includes_dc_growth = model.Property(
    f"{DemandForecast} includes DC growth {Boolean:includes_dc_growth}")

# LoadHistory
LoadHistory = model.Concept("LoadHistory", identify_by={"id": String})
LoadHistory.reading_date = model.Property(f"{LoadHistory} has reading date {String:reading_date}")
LoadHistory.load_mw = model.Property(f"{LoadHistory} has load {Float:load_mw} MW")
LoadHistory.temperature_f = model.Property(f"{LoadHistory} has temperature {Float:temperature_f} F")
LoadHistory.is_peak_season = model.Property(f"{LoadHistory} is peak season {Boolean:is_peak_season}")
LoadHistory.substation = model.Relationship(f"{LoadHistory} measured at {Substation}")

# DCAnnouncement
DCAnnouncement = model.Concept("DCAnnouncement", identify_by={"id": String})
DCAnnouncement.hyperscaler = model.Property(
    f"{DCAnnouncement} from hyperscaler {String:hyperscaler}")
DCAnnouncement.announced_date = model.Property(
    f"{DCAnnouncement} announced on {String:announced_date}")
DCAnnouncement.announced_mw = model.Property(f"{DCAnnouncement} announcing {Float:announced_mw} MW")
DCAnnouncement.substation = model.Relationship(f"{DCAnnouncement} targets {Substation}")

# Typed endpoints for the corridor search: substations hosting a generator
# (source) and a DC request (sink).
GeneratorSubstation = model.Concept("GeneratorSubstation", extends=[Substation])
DCSubstation = model.Concept("DCSubstation", extends=[Substation])

# InvestmentLevel Scenario Concept: 5 budget levels
InvestmentLevel = model.Concept("InvestmentLevel", identify_by={"name": String})
InvestmentLevel.budget_cap = model.Property(f"{InvestmentLevel} has {Float:budget_cap}")
InvestmentLevel.next_level = model.Relationship(
    f"{InvestmentLevel:level} is followed by {InvestmentLevel:next_level}"
)

# InvestmentPortfolio: one row per InvestmentLevel scenario, derived from the solve.
InvestmentPortfolio = model.Concept(
    "InvestmentPortfolio", identify_by={"investment_level_name": String}
)
InvestmentPortfolio.investment_level = model.Relationship(
    f"{InvestmentPortfolio} for {InvestmentLevel}"
)
InvestmentPortfolio.dc_count = model.Property(f"{InvestmentPortfolio} has {Integer:dc_count}")
InvestmentPortfolio.total_mw = model.Property(f"{InvestmentPortfolio} has {Float:total_mw}")
InvestmentPortfolio.annual_revenue = model.Property(
    f"{InvestmentPortfolio} has {Float:annual_revenue}"
)
InvestmentPortfolio.upgrade_cost = model.Property(
    f"{InvestmentPortfolio} has {Float:upgrade_cost}"
)
InvestmentPortfolio.net_value = model.Property(f"{InvestmentPortfolio} has {Float:net_value}")
InvestmentPortfolio.marginal_per_m_to_next_level = model.Property(
    f"{InvestmentPortfolio} has {Float:marginal_per_m_to_next_level}"
)
InvestmentPortfolio.marginal_drop = model.Property(f"{InvestmentPortfolio} has {Float:marginal_drop}")
InvestmentPortfolio.is_knee_point = model.Relationship(f"{InvestmentPortfolio} is the knee point")
