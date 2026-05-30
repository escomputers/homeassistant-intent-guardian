# Home Assistant Intent Guardian — Bozza concettuale

## 1. Intro: perché esiste questa idea

Home Assistant ha risolto un problema enorme: integrare dispositivi di brand diversi in un sistema aperto, locale e flessibile. Però resta ancora difficile per utenti non tecnici, famiglie, piccoli bar, B&B, ristoranti, negozi o aziende agricole familiari che hanno bisogni concreti ma non vogliono ragionare in termini di YAML, trigger, condizioni, entità, stati `unavailable`, retry e failure mode.

Il problema non è solo “creare un’automazione”. Il problema è trasformare un bisogno umano in una regola affidabile, comprensibile e realmente deployabile.

Esempi di bisogni reali:

* “Avvisami se manca corrente al bar.”
* “Se il freezer supera una certa temperatura, avvisa prima me e poi un’altra persona.”
* “Dopo il tramonto le luci del giardino devono essere accese fino alle 23:30.”
* “Se un dispositivo critico è offline, dimmelo.”
* “Se Home Assistant si riavvia, controlla che le cose importanti siano nello stato corretto.”

L’obiettivo del software è creare un layer sopra Home Assistant che permetta all’utente di esprimere un intento tramite form guidati, eventualmente aiutati da AI, e trasformarlo in automazioni Home Assistant robuste solo dopo validazione, classificazione del rischio, spiegazione e approvazione.

Il punto centrale non è usare l’AI per scrivere YAML liberamente. Il valore sta nel costruire una pipeline controllata:

```text
utente → template/form → spec interna → validazione → generazione YAML → verifica → deploy → monitoraggio
```

L’AI può aiutare a interpretare e completare l’intento. La parte critica deve però essere deterministica: validatore, modello di rischio, compilatore YAML, verifica e deploy.

---

## 2. Principio di base

Il software non deve chiedere all’utente di pensare come Home Assistant.

Non deve partire da:

```text
trigger / condition / action
```

Deve partire da:

```text
cosa vuoi che sia vero?
```

Esempio:

```text
Dopo il tramonto e prima delle 23:30, le luci del giardino devono essere accese.
```

Il sistema traduce questo bisogno in una regola robusta che include, se necessario:

* controllo periodico;
* recupero dopo riavvio di Home Assistant;
* retry;
* gestione `unavailable`;
* notifica in caso di fallimento;
* spiegazione leggibile;
* audit log;
* rollback o rimozione sicura.

---

## 3. Sequenza logica del software

### 3.1 Scelta template

L’utente sceglie un template tra quelli supportati.

Esempi V1:

* Mantieni uno stato desiderato, per esempio luci accese dopo il tramonto.
* Avvisami se un dispositivo è offline.
* Avvisami se una temperatura supera una soglia.

Esempi futuri:

* Mancanza corrente.
* Perdita acqua.
* Escalation notifiche multi-persona.
* Routine business, per esempio apertura/chiusura bar.
* Watchdog esterno di Home Assistant.

### 3.2 Form guidato

Il sistema raccoglie le informazioni necessarie con domande semplici.

Esempio per luci giardino:

```text
Quale oggetto vuoi controllare? → Luci giardino
Quando deve essere attivo? → Dopo il tramonto
Fino a che ora? → 23:30
Ogni quanto ricontrollare? → Ogni 10 minuti
Cosa fare se fallisce? → Avvisami
```

L’LLM può essere usato per aiutare l’utente a compilare il form, ma il risultato deve essere sempre convertito in una struttura rigida e validabile.

### 3.3 Ricerca entità candidate

Il software interroga Home Assistant e cerca le entità più plausibili usando:

* `entity_id`;
* nome descrittivo;
* dominio, per esempio `light`, `switch`, `sensor`;
* area;
* device class;
* unità di misura;
* integrazione sorgente;
* stato recente;
* eventuali label già presenti in Home Assistant.

Il sistema non deve scegliere alla cieca. Deve proporre candidati con una confidenza.

Esempio:

```text
Ho trovato queste possibili entità:

1. light.luci_giardino
   Nome: Luci giardino
   Area: Esterno
   Confidenza: alta

2. switch.shelly_garden_01
   Nome: Shelly giardino
   Area: Esterno
   Confidenza: media
```

In caso di ambiguità, l’utente conferma.

### 3.4 Wizard di classificazione entità

Se l’entità non è ancora classificata, parte un wizard.

Domande principali:

```text
Questa entità cos’è nella vita reale?
[ Luce ] [ Presa ] [ Frigo/freezer ] [ Pompa ] [ Allarme ] [ Router ] [ Sensore ] [ Altro ]

Livello impatto:
[ Basso ] [ Medio ] [ Alto ] [ Critico ]

Permessi:
[ Può solo leggere ]
[ Può notificare ]
[ Può accendere ]
[ Può spegnere ]
[ Mai modificare automaticamente ]
```

Il wizard non deve obbligare l’utente a classificare tutta la casa subito. Deve comparire quando una nuova automazione usa un’entità non ancora conosciuta.

### 3.5 Catalogo semantico entità

Le scelte dell’utente vengono salvate in un catalogo interno.

Esempio:

```yaml
entity_id: light.luci_giardino
real_world_name: Luci giardino
category: light
impact: low
permissions:
  read: true
  notify: true
  turn_on: true
  turn_off: true
  auto_modify: true
```

Esempio ad alto impatto:

```yaml
entity_id: switch.pompa_pozzo
real_world_name: Pompa pozzo
category: pump
impact: high
permissions:
  read: true
  notify: true
  turn_on: false
  turn_off: true
  auto_modify: false
```

Questo catalogo è fondamentale. Serve a evitare che il sistema tratti tutte le entità allo stesso modo. Uno `switch` può essere una lampada, una pompa, un freezer, una presa router o qualcosa di pericoloso.

### 3.6 Creazione spec interna

Il sistema crea una spec interna. Non è YAML Home Assistant finale. È un contratto logico semplice, limitato e validabile.

Esempio:

```yaml
type: desired_state
name: garden_lights_after_sunset

target:
  entity_id: light.luci_giardino
  desired_state: "on"

active_when:
  sun: below_horizon
  before_time: "23:30"

reconciliation:
  on_homeassistant_start: true
  interval: "10m"

failure_handling:
  retries: 3
  retry_delay: "30s"
  notify:
    - person.emiliano
```

La spec deve appartenere a un set limitato di pattern supportati. Il sistema non deve accettare automazioni arbitrarie nella V1.

Pattern iniziali consigliati:

* `desired_state`
* `offline_monitor`
* `threshold_alert`

Pattern successivi:

* `power_outage_monitor`
* `leak_alert`
* `escalation_notification`
* `business_open_close_routine`

### 3.7 Validazione

Il validatore controlla la spec prima della generazione YAML.

Controlli principali:

* l’entità esiste in Home Assistant;
* l’entità è classificata nel catalogo;
* i permessi permettono l’azione richiesta;
* l’impatto richiede conferme aggiuntive;
* il template supporta quel tipo di entità;
* sono definiti retry, timeout e comportamento in caso di fallimento;
* non ci sono loop evidenti;
* non si generano notifiche infinite;
* esiste una strategia per riavvio Home Assistant o stato `unavailable`, dove applicabile.

Esempio errore bloccante:

```text
L’entità switch.pompa_pozzo è classificata come alto impatto.
Il permesso di accensione automatica non è consentito.
Questa automazione non può essere applicata.
```

### 3.8 Repair loop

Se il validatore trova problemi riparabili, il sistema può proporre una correzione.

Esempi:

* manca la notifica in caso di fallimento;
* manca il comportamento quando l’entità è `unavailable`;
* manca una finestra temporale;
* il nome dell’entità è ambiguo;
* il livello di impatto richiede conferma aggiuntiva.

L’LLM può aiutare a proporre una patch della spec, ma il validatore deve ricontrollare sempre. Il validatore resta l’autorità finale.

Se il problema non è risolvibile, il sistema deve bloccare e spiegare il motivo.

### 3.9 Generazione YAML

Quando la spec è valida, il compiler genera YAML Home Assistant tramite template controllati.

La generazione finale non deve essere libera via LLM.

Flusso:

```text
spec valida → compiler deterministico → YAML Home Assistant
```

### 3.10 Validazione YAML

Dopo la generazione:

* parsing YAML;
* controllo entità/servizi;
* controllo configurazione Home Assistant dove possibile;
* staging del file generato;
* backup prima del deploy.

Il file generato dovrebbe essere gestito dal software, per esempio:

```text
/config/packages/intentguard/generated/garden_lights_after_sunset.yaml
```

Con header esplicito:

```yaml
# Managed by IntentGuard
# Do not edit manually
# Policy ID: garden_lights_after_sunset
```

### 3.11 Simulazione e spiegazione

Prima del deploy, l’utente non deve leggere lo YAML. Deve vedere cosa succederà.

Esempio:

```text
Dopo il tramonto e prima delle 23:30 controllerò che le luci del giardino siano accese.

Se Home Assistant si riavvia dopo il tramonto, ricontrollerò.

Ogni 10 minuti controllerò lo stato.

Se le luci sono spente, proverò ad accenderle.

Se dopo 3 tentativi non risultano accese, ti invierò una notifica.
```

Esempi di scenari:

```text
Scenario: Home Assistant era spento al tramonto e torna online alle 19:10.
Risultato: ricontrollo e provo ad accendere le luci.

Scenario: le luci non rispondono.
Risultato: provo 3 volte, poi notifico errore.

Scenario: sono le 23:45.
Risultato: non accendo le luci.
```

### 3.12 Conferma utente

La conferma dipende dal livello di impatto.

* Basso: conferma semplice.
* Medio: conferma con riassunto.
* Alto: conferma esplicita, warning e audit log.
* Critico: bloccato di default o modalità esperto/installatore.

Esempi critici:

* disattivare un allarme;
* aprire una serratura;
* attivare una pompa;
* spegnere dispositivi business-critical;
* agire su dispositivi safety-related.

### 3.13 Deploy

Il deploy deve essere controllato.

Passaggi:

* backup configurazione precedente;
* scrittura file managed;
* controllo configurazione;
* reload automazioni dove possibile;
* verifica che l’automazione sia attiva;
* audit log;
* rollback se qualcosa fallisce.

### 3.14 Monitoraggio post-deploy

Dopo il deploy, il sistema continua a monitorare le automazioni gestite.

Controlli:

* automazione ancora presente;
* entità ancora esistenti;
* entità troppo spesso `unavailable`;
* errori recenti;
* ultime esecuzioni;
* notifiche fallite;
* policy mai eseguita;
* dipendenze degradate.

Esempio:

```text
La protezione “Luci giardino dopo tramonto” è degradata.
Motivo: light.luci_giardino è unavailable da 2 ore.
```

---

## 4. Feature opzionale post-V1: watchdog esterno di Home Assistant

Il software dovrebbe poter girare anche fuori da Home Assistant, per esempio su un host dedicato, NAS, mini PC, Raspberry Pi separato o VPS leggero.

Questo abilita una feature importante: controllare se Home Assistant è operativo nei momenti critici.

Esempio:

```text
La policy “Luci giardino dopo tramonto” è attiva tra tramonto e 23:30.
Se Home Assistant non risponde in quella finestra, il sistema esterno può notificare l’utente.
```

Non basta fare un ping generico. Serve un heartbeat contestuale.

Il sistema deve sapere:

* quali policy sono attive in quel momento;
* quali dipendenze servono;
* se Home Assistant è raggiungibile;
* se la sua API risponde;
* se una failure avviene durante una finestra critica.

Esempio notifica:

```text
Home Assistant non è raggiungibile durante una finestra critica:
“Luci giardino dopo tramonto”.
Non posso verificare né correggere lo stato delle luci.
```

Questa feature richiede canali di notifica indipendenti da Home Assistant, per esempio Telegram, Pushover, email SMTP, SMS provider o altro.

Limite importante:

```text
Se il software esterno, Home Assistant, router e modem sono tutti sulla stessa corrente e senza UPS, il watchdog non può notificare durante un blackout totale.
```

Per piccoli business, bar, B&B o aziende agricole, il valore aumenta se il watchdog gira:

* su host separato;
* sotto UPS;
* con connessione alternativa;
* oppure su VPS/cloud leggero con heartbeat minimale dal sito locale.

Questa feature è utile, ma non dovrebbe essere V1. Prima va validato il core: template, catalogo entità, validazione, generazione YAML e deploy.

---

## 5. Bozza tecnica

### 5.1 Scelta architetturale generale

La V1 nasce come Home Assistant add-on, ma il cuore del software deve essere progettato come libreria separabile.

Obiettivo:

```text
stesso core logico
+ primo adapter: Home Assistant add-on
+ futuro adapter: servizio esterno / watchdog / deploy remoto
```

Separazione consigliata:

```text
intentguard-core/
  modelli spec
  catalogo semantico entità
  pattern supportati
  risk engine
  validator
  repair planner
  compiler YAML
  simulatore
  summary/reporting
  test

intentguard-ha-addon/
  UI
  Home Assistant adapter
  storage SQLite
  gestione configurazione add-on
  deploy manager
  reload/check configurazione
  monitoraggio base

future intentguard-external/
  servizio esterno
  adapter Home Assistant remoto
  heartbeat/watchdog HA
  notifiche indipendenti da HA
  applicazione remota/assistita degli YAML generati
```

Il core non deve sapere se gira dentro un add-on o fuori. Deve ricevere dati già preparati e restituire risultati validabili.

Il core non dovrebbe occuparsi direttamente di:

* UI;
* chiamate API a Home Assistant;
* lettura/scrittura file;
* deploy reale;
* reload automazioni;
* notifiche reali;
* chiamate LLM;
* storage fisico.

Queste responsabilità stanno nell’add-on V1 o, in futuro, nel servizio esterno.

### 5.2 Responsabilità del core

Il core è la parte più importante e innovativa. Deve trasformare input controllati in output deployabili.

Flusso logico:

```text
input utente/template
+ snapshot Home Assistant
+ catalogo semantico
+ configurazione capacità runtime
↓
spec interna
↓
validazione
↓
risk assessment
↓
eventuale repair plan
↓
compilazione YAML
↓
simulazione/spiegazione
↓
risultato pronto per deploy
```

Funzioni pubbliche indicative:

```python
match_entities(intent, ha_snapshot, catalog) -> list[EntityCandidate]
build_spec(template_id, user_inputs, selected_entities, catalog) -> PolicySpec
validate_spec(spec, ha_snapshot, catalog, runtime_capabilities) -> ValidationResult
assess_risk(spec, catalog) -> RiskAssessment
plan_repair(validation_result) -> RepairPlan
compile_policy(spec, catalog) -> CompiledAutomation
simulate_policy(spec, risk) -> SimulationReport
render_summary(spec, risk, simulation) -> HumanReadableSummary
```

Il core deve essere testabile senza Home Assistant reale, usando fixture JSON/YAML.

### 5.3 Configurazione e profili di deploy

Il software deve prevedere una configurazione che descriva le capacità del runtime corrente.

Esempio add-on V1:

```yaml
deployment_profile:
  mode: home_assistant_addon

  capabilities:
    can_write_ha_config: true
    can_reload_automations: true
    can_run_ha_config_check: true
    has_independent_notifications: false
    can_watchdog_ha_from_outside: false
```

Esempio futuro servizio esterno:

```yaml
deployment_profile:
  mode: external_service

  capabilities:
    can_write_ha_config: false
    can_apply_via_ha_api: true
    can_reload_automations: true
    has_independent_notifications: true
    can_watchdog_ha_from_outside: true
```

Il core può usare queste capability per validare cosa è possibile fare. I dettagli concreti del deploy restano però nell’adapter.

### 5.4 Storage V1

Per la V1 si usa SQLite dentro l’add-on.

Percorso consigliato:

```text
/data/intentguard.db
```

La configurazione add-on può stare in:

```text
/data/options.json
```

Gli YAML generati restano file managed dentro la configurazione Home Assistant, per esempio:

```text
/config/packages/intentguard/generated/*.yaml
```

SQLite non è obbligatorio per un prototipo minimale, ma è consigliato per una V1 seria perché il prodotto deve salvare catalogo entità, policy, versioni, audit e stato deploy.

Tabelle indicative:

```text
entities
entity_classifications
policies
policy_versions
deployments
audit_events
validation_results
runtime_checks
```

Esempio schema logico:

```text
entities
- entity_id
- friendly_name
- domain
- area
- device_class
- last_seen

entity_classifications
- entity_id
- real_world_name
- category
- impact
- permissions_json

policies
- policy_id
- name
- pattern_type
- status
- current_version_id

policy_versions
- version_id
- policy_id
- spec_json
- generated_yaml
- yaml_hash
- created_at

deployments
- deployment_id
- policy_version_id
- status
- deployed_at
- error_message
```

SQLite tiene stato, catalogo, versioni e audit. Home Assistant continua a leggere gli YAML managed.

### 5.5 Linguaggio e stack consigliato

Backend/core:

```text
Python
Pydantic
Jinja2
ruamel.yaml
pytest
```

Add-on/API/UI backend:

```text
FastAPI
SQLite
SQLModel o SQLAlchemy leggero
```

Frontend:

```text
UI web semplice
```

Possibili scelte:

* React/TypeScript per una UI più strutturata;
* HTMX + template server-side per MVP più rapido;
* dashboard minimale integrata nell’add-on.

Per MVP, meglio privilegiare semplicità e velocità.

Motivi delle scelte:

* Python è coerente con l’ecosistema Home Assistant;
* Pydantic permette spec rigide e validabili;
* Jinja2 permette generazione YAML deterministica;
* SQLite è sufficiente per V1;
* FastAPI è semplice per esporre API interne all’UI;
* pytest permette di testare core, validator e compiler senza HA reale.

### 5.6 Componenti principali

```text
Intent/Form Layer
Entity Discovery
Entity Semantic Catalog
Policy Spec Builder
Risk Engine
Validator
Repair Planner
Compiler
YAML Validator
Deploy Manager
Runtime Monitor
Audit Log
```

#### Intent/Form Layer

Gestisce template, form guidati e, in futuro, input in linguaggio naturale.

#### Entity Discovery

Interroga Home Assistant per ottenere entità, stati, aree, servizi e metadati utili.

#### Entity Semantic Catalog

Salva la mappatura tra entità tecniche Home Assistant e oggetti reali.

Esempio:

```text
switch.shelly_abc123 → Pompa pozzo → alto impatto → non accendere automaticamente
```

#### Policy Spec Builder

Crea una spec interna a partire da template, form e catalogo entità.

#### Risk Engine

Assegna livello di impatto e regole di sicurezza.

Esempi:

```text
light.turn_on → basso
sensor temperature read → basso
switch generico turn_on → medio/alto se non classificato
pump turn_on → alto
alarm disarm → critico
lock unlock → critico
```

#### Validator

Controlla spec, entità, permessi, rischio, failure handling e compatibilità con il template.

#### Repair Planner

Classifica gli errori del validatore:

* riparabile automaticamente;
* richiede scelta utente;
* può essere passato all’LLM come proposta di patch;
* bloccante.

L’LLM può suggerire una modifica, ma ogni patch torna sempre al validatore.

#### Compiler

Genera YAML Home Assistant da spec valide usando template deterministici.

#### YAML Validator

Controlla che il risultato sia valido prima del deploy.

#### Deploy Manager

Sta nell’add-on, non nel core. Scrive file managed, esegue backup, reload, verifica e rollback.

#### Runtime Monitor

Sta nell’add-on V1 o nel futuro servizio esterno. Controlla lo stato delle policy dopo il deploy.

#### Audit Log

Registra:

* chi ha creato la policy;
* quando è stata modificata;
* quale spec ha generato quale YAML;
* esiti di validazione;
* deploy;
* errori;
* rollback.

### 5.7 Ruolo dell’LLM

L’LLM non deve essere il motore di esecuzione.

Ruoli ammessi:

* aiutare l’utente a compilare il form;
* interpretare testo libero;
* proporre candidati tra entità simili;
* spiegare errori in linguaggio umano;
* suggerire fix alla spec.

Ruoli da evitare in V1:

* generare YAML finale liberamente;
* deployare senza validazione;
* decidere autonomamente azioni su entità ad alto impatto;
* comandare direttamente dispositivi.

### 5.8 Pattern V1 consigliati

Per ridurre complessità, la V1 dovrebbe supportare pochi pattern ma solidi.

#### 1. Desired State

Esempio:

```text
Mantieni le luci giardino accese dopo il tramonto fino alle 23:30.
```

#### 2. Offline Monitor

Esempio:

```text
Avvisami se il freezer bar non risponde per più di 15 minuti.
```

#### 3. Threshold Alert

Esempio:

```text
Avvisami se il freezer supera -10 °C per più di 15 minuti.
```

Questi tre pattern bastano per validare:

* scelta entità;
* wizard classificazione;
* catalogo semantico;
* risk engine;
* validazione;
* generazione YAML;
* deploy;
* monitoraggio.

---

## 6. Decisioni prese per la V1

Nome provvisorio:

```text
IntentGuard
```

Target iniziale:

```text
utenti Home Assistant evoluti, famiglie con esigenze concrete, piccoli business, installatori smart home leggeri
```

Scelta architetturale V1:

```text
Home Assistant add-on come primo packaging ufficiale.
Core progettato come libreria separabile e riusabile anche fuori da Home Assistant.
```

Motivo:

```text
La V1 deve validare il cuore del prodotto: template, catalogo entità, spec interna, validatore, risk engine, compiler YAML, deploy controllato e monitoraggio base.
```

Il core è la parte più importante e innovativa. L’add-on è il primo contenitore pratico per distribuirlo e testarlo.

Struttura consigliata:

```text
intentguard-core/
  modelli spec
  catalogo entità
  risk engine
  validator
  compiler YAML
  simulatore
  test

intentguard-ha-addon/
  UI
  HA adapter
  deploy manager
  gestione config
  packaging add-on

future intentguard-external/
  servizio esterno
  heartbeat Home Assistant
  notifiche indipendenti
  deploy remoto/assistito delle automazioni generate
```

La futura modalità esterna non deve essere un prodotto diverso. Deve riusare lo stesso core e avere un adapter capace di applicare su Home Assistant gli YAML generati e validati.

Non target V1:

```text
sostituto di Home Assistant
agente AI che controlla direttamente casa
builder universale di qualunque automazione possibile
watchdog esterno completo
sistema safety-critical certificato
```

MVP consigliato:

```text
Add-on Home Assistant con UI semplice, tre template iniziali, catalogo entità, validatore, compiler YAML, deploy controllato e monitoraggio base.
```

Feature post-V1:

```text
runtime esterno / watchdog HA / heartbeat contestuale / notifiche indipendenti da HA / adapter per deploy da host esterno
```

---

## 7. Sintesi finale

IntentGuard è un layer sopra Home Assistant pensato per trasformare bisogni umani in automazioni robuste, spiegabili e deployabili.

La parte importante non è far scrivere YAML all’AI. La parte importante è impedire che una richiesta ambigua o rischiosa diventi automazione reale senza passare da classificazione entità, validazione, risk scoring, spiegazione e conferma.

Prima il sistema deve capire cosa sono le entità nella vita reale. Poi può costruire automazioni sopra quella mappa.

La V1 deve essere stretta, concreta e solida. Meglio tre pattern fatti bene che un generatore universale fragile.

---

## 8. Development status

Stato attuale del repository:

* walking skeleton iniziale con package `intentguard_core` puro e testabile;
* adapter add-on minimale con FastAPI, endpoint `GET /health` e inizializzazione SQLite;
* CI base con `pytest`.

Fuori scope in questa fase:

* LLM e interpretazione linguaggio naturale;
* entity discovery da Home Assistant;
* generazione YAML finale;
* deploy, monitoraggio completo e integrazione API Home Assistant.
