import SwiftUI

struct LeagueBranding: Decodable {
    let code: String
    let logo: URL
    let teams: [TeamBranding]
}

struct TeamBranding: Decodable {
    let id: Int
    let names: [String]
    let logo: URL
}


enum LocalCrestCatalog {
    private static let assetsByLeague: [String: [String: String]] = [
        "D1": [
            "1fcheidenheim": "BundesligaHeidenheim",
            "1fcheidenheim1846": "BundesligaHeidenheim",
            "1fckoln": "BundesligaKoln",
            "1fcunionberlin": "BundesligaUnionBerlin",
            "augsburg": "BundesligaAugsburg",
            "bayer04leverkusen": "BundesligaLeverkusen",
            "bayerleverkusen": "BundesligaLeverkusen",
            "bayernmunchen": "BundesligaBayernMunich",
            "bayernmunich": "BundesligaBayernMunich",
            "bochum": "BundesligaBochum",
            "borussiadortmund": "BundesligaDortmund",
            "borussiamgladbach": "BundesligaMonchengladbach",
            "borussiamonchengladbach": "BundesligaMonchengladbach",
            "dortmund": "BundesligaDortmund",
            "einfrankfurt": "BundesligaEintrachtFrankfurt",
            "eintrachtfrankfurt": "BundesligaEintrachtFrankfurt",
            "elversberg": "BundesligaElversberg",
            "fcaugsburg": "BundesligaAugsburg",
            "fcbayernmunchen": "BundesligaBayernMunich",
            "fcheidenheim": "BundesligaHeidenheim",
            "fckoln": "BundesligaKoln",
            "fcstpauli": "BundesligaStPauli",
            "frankfurt": "BundesligaEintrachtFrankfurt",
            "freiburg": "BundesligaFreiburg",
            "fsvmainz05": "BundesligaMainz",
            "hamburg": "BundesligaHamburg",
            "hamburgersv": "BundesligaHamburg",
            "heidenheim": "BundesligaHeidenheim",
            "hoffenheim": "BundesligaHoffenheim",
            "holsteinkiel": "BundesligaHolsteinKiel",
            "koln": "BundesligaKoln",
            "leverkusen": "BundesligaLeverkusen",
            "mainz": "BundesligaMainz",
            "mainz05": "BundesligaMainz",
            "mgladbach": "BundesligaMonchengladbach",
            "monchengladbach": "BundesligaMonchengladbach",
            "paderborn": "BundesligaPaderborn",
            "rbleipzig": "BundesligaRBLeipzig",
            "scfreiburg": "BundesligaFreiburg",
            "schalke04": "BundesligaSchalke04",
            "scpaderborn": "BundesligaPaderborn",
            "stpauli": "BundesligaStPauli",
            "stuttgart": "BundesligaStuttgart",
            "svelversberg": "BundesligaElversberg",
            "svwerderbremen": "BundesligaWerderBremen",
            "tsg1899hoffenheim": "BundesligaHoffenheim",
            "tsghoffenheim": "BundesligaHoffenheim",
            "unionberlin": "BundesligaUnionBerlin",
            "vfbstuttgart": "BundesligaStuttgart",
            "vflbochum": "BundesligaBochum",
            "vflbochum1848": "BundesligaBochum",
            "vflwolfsburg": "BundesligaWolfsburg",
            "werder": "BundesligaWerderBremen",
            "werderbremen": "BundesligaWerderBremen",
            "wolfsburg": "BundesligaWolfsburg",
        ],
        "E0": [
            "afcbournemouth": "LocalE0_afcbournemouth",
            "arsenal": "LocalE0_arsenalfc",
            "arsenalfc": "LocalE0_arsenalfc",
            "astonvilla": "LocalE0_astonvilla",
            "bournemouth": "LocalE0_afcbournemouth",
            "brentford": "LocalE0_brentfordfc",
            "brentfordfc": "LocalE0_brentfordfc",
            "brighton": "LocalE0_brightonhovealbion",
            "brightonhovealbion": "LocalE0_brightonhovealbion",
            "burnley": "LocalE0_burnleyfc",
            "burnleyfc": "LocalE0_burnleyfc",
            "chelsea": "LocalE0_chelseafc",
            "chelseafc": "LocalE0_chelseafc",
            "crystalpalace": "LocalE0_crystalpalace",
            "everton": "LocalE0_evertonfc",
            "evertonfc": "LocalE0_evertonfc",
            "fulham": "LocalE0_fulhamfc",
            "fulhamfc": "LocalE0_fulhamfc",
            "leedsunited": "LocalE0_leedsunited",
            "liverpool": "LocalE0_liverpoolfc",
            "liverpoolfc": "LocalE0_liverpoolfc",
            "manchestercity": "LocalE0_manchestercity",
            "manchesterunited": "LocalE0_manchesterunited",
            "mancity": "LocalE0_manchestercity",
            "manunited": "LocalE0_manchesterunited",
            "manutd": "LocalE0_manchesterunited",
            "newcastle": "LocalE0_newcastleunited",
            "newcastleunited": "LocalE0_newcastleunited",
            "nottinghamforest": "LocalE0_nottinghamforest",
            "nottmforest": "LocalE0_nottinghamforest",
            "spurs": "LocalE0_tottenhamhotspur",
            "sunderland": "LocalE0_sunderlandafc",
            "sunderlandafc": "LocalE0_sunderlandafc",
            "tottenham": "LocalE0_tottenhamhotspur",
            "tottenhamhotspur": "LocalE0_tottenhamhotspur",
            "westham": "LocalE0_westhamunited",
            "westhamunited": "LocalE0_westhamunited",
            "wolverhamptonwanderers": "LocalE0_wolverhamptonwanderers",
            "wolves": "LocalE0_wolverhamptonwanderers",
        ],
        "SP1": [
            "alaves": "LocalSP1_deportivoalaves",
            "athbilbao": "LocalSP1_athleticbilbao",
            "athleticbilbao": "LocalSP1_athleticbilbao",
            "atleticodemadrid": "LocalSP1_atleticodemadrid",
            "atleticomadrid": "LocalSP1_atleticodemadrid",
            "barcelona": "LocalSP1_fcbarcelona",
            "betis": "LocalSP1_realbetisbalompie",
            "caosasuna": "LocalSP1_caosasuna",
            "celta": "LocalSP1_celtadevigo",
            "celtadevigo": "LocalSP1_celtadevigo",
            "deportivoalaves": "LocalSP1_deportivoalaves",
            "elche": "LocalSP1_elchecf",
            "elchecf": "LocalSP1_elchecf",
            "espanol": "LocalSP1_rcdespanyolbarcelona",
            "espanyol": "LocalSP1_rcdespanyolbarcelona",
            "fcbarcelona": "LocalSP1_fcbarcelona",
            "getafe": "LocalSP1_getafecf",
            "getafecf": "LocalSP1_getafecf",
            "girona": "LocalSP1_gironafc",
            "gironafc": "LocalSP1_gironafc",
            "levante": "LocalSP1_levanteud",
            "levanteud": "LocalSP1_levanteud",
            "mallorca": "LocalSP1_rcdmallorca",
            "osasuna": "LocalSP1_caosasuna",
            "rayovallecano": "LocalSP1_rayovallecano",
            "rcdespanyolbarcelona": "LocalSP1_rcdespanyolbarcelona",
            "rcdmallorca": "LocalSP1_rcdmallorca",
            "realbetis": "LocalSP1_realbetisbalompie",
            "realbetisbalompie": "LocalSP1_realbetisbalompie",
            "realmadrid": "LocalSP1_realmadrid",
            "realoviedo": "LocalSP1_realoviedo",
            "realsociedad": "LocalSP1_realsociedad",
            "sevilla": "LocalSP1_sevillafc",
            "sevillafc": "LocalSP1_sevillafc",
            "sociedad": "LocalSP1_realsociedad",
            "valencia": "LocalSP1_valenciacf",
            "valenciacf": "LocalSP1_valenciacf",
            "vallecano": "LocalSP1_rayovallecano",
            "villarreal": "LocalSP1_villarrealcf",
            "villarrealcf": "LocalSP1_villarrealcf",
        ],
        "I1": [
            "acffiorentina": "LocalI1_acffiorentina",
            "acmilan": "LocalI1_acmilan",
            "asroma": "LocalI1_asroma",
            "atalanta": "LocalI1_atalantabc",
            "atalantabc": "LocalI1_atalantabc",
            "bologna": "LocalI1_bolognafc1909",
            "bolognafc1909": "LocalI1_bolognafc1909",
            "cagliari": "LocalI1_cagliaricalcio",
            "cagliaricalcio": "LocalI1_cagliaricalcio",
            "como": "LocalI1_como1907",
            "como1907": "LocalI1_como1907",
            "cremonese": "LocalI1_uscremonese",
            "fiorentina": "LocalI1_acffiorentina",
            "genoa": "LocalI1_genoacfc",
            "genoacfc": "LocalI1_genoacfc",
            "hellasverona": "LocalI1_hellasverona",
            "inter": "LocalI1_intermilan",
            "intermilan": "LocalI1_intermilan",
            "juventus": "LocalI1_juventusfc",
            "juventusfc": "LocalI1_juventusfc",
            "lazio": "LocalI1_sslazio",
            "lecce": "LocalI1_uslecce",
            "milan": "LocalI1_acmilan",
            "napoli": "LocalI1_sscnapoli",
            "parma": "LocalI1_parmacalcio1913",
            "parmacalcio1913": "LocalI1_parmacalcio1913",
            "pisa": "LocalI1_pisasportingclub",
            "pisasportingclub": "LocalI1_pisasportingclub",
            "roma": "LocalI1_asroma",
            "sassuolo": "LocalI1_ussassuolo",
            "sscnapoli": "LocalI1_sscnapoli",
            "sslazio": "LocalI1_sslazio",
            "torino": "LocalI1_torinofc",
            "torinofc": "LocalI1_torinofc",
            "udinese": "LocalI1_udinesecalcio",
            "udinesecalcio": "LocalI1_udinesecalcio",
            "uscremonese": "LocalI1_uscremonese",
            "uslecce": "LocalI1_uslecce",
            "ussassuolo": "LocalI1_ussassuolo",
            "verona": "LocalI1_hellasverona",
        ],
        "F1": [
            "ajauxerre": "LocalF1_ajauxerre",
            "angers": "LocalF1_angerssco",
            "angerssco": "LocalF1_angerssco",
            "asmonaco": "LocalF1_asmonaco",
            "auxerre": "LocalF1_ajauxerre",
            "brest": "LocalF1_stadebrestois29",
            "fclorient": "LocalF1_fclorient",
            "fcmetz": "LocalF1_fcmetz",
            "fcnantes": "LocalF1_fcnantes",
            "fctoulouse": "LocalF1_fctoulouse",
            "lehavre": "LocalF1_lehavreac",
            "lehavreac": "LocalF1_lehavreac",
            "lens": "LocalF1_rclens",
            "lille": "LocalF1_losclille",
            "lorient": "LocalF1_fclorient",
            "losclille": "LocalF1_losclille",
            "lyon": "LocalF1_olympiquelyon",
            "marseille": "LocalF1_olympiquemarseille",
            "metz": "LocalF1_fcmetz",
            "monaco": "LocalF1_asmonaco",
            "nantes": "LocalF1_fcnantes",
            "nice": "LocalF1_ogcnice",
            "ogcnice": "LocalF1_ogcnice",
            "olympiquelyon": "LocalF1_olympiquelyon",
            "olympiquemarseille": "LocalF1_olympiquemarseille",
            "parisfc": "LocalF1_parisfc",
            "parissaintgermain": "LocalF1_parissaintgermain",
            "parissg": "LocalF1_parissaintgermain",
            "psg": "LocalF1_parissaintgermain",
            "rclens": "LocalF1_rclens",
            "rcstrasbourgalsace": "LocalF1_rcstrasbourgalsace",
            "rennes": "LocalF1_staderennaisfc",
            "stadebrestois29": "LocalF1_stadebrestois29",
            "staderennaisfc": "LocalF1_staderennaisfc",
            "strasbourg": "LocalF1_rcstrasbourgalsace",
            "toulouse": "LocalF1_fctoulouse",
        ],
        "T1": [
            "alanyaspor": "LocalT1_alanyaspor",
            "antalyaspor": "LocalT1_antalyaspor",
            "basaksehir": "LocalT1_basaksehirfk",
            "basaksehirfk": "LocalT1_basaksehirfk",
            "besiktas": "LocalT1_besiktasjk",
            "besiktasjk": "LocalT1_besiktasjk",
            "caykurrizespor": "LocalT1_caykurrizespor",
            "eyupspor": "LocalT1_eyupspor",
            "fatihkaragumruk": "LocalT1_fatihkaragumruk",
            "fenerbahce": "LocalT1_fenerbahce",
            "galatasaray": "LocalT1_galatasaray",
            "gaziantep": "LocalT1_gaziantepfk",
            "gaziantepfk": "LocalT1_gaziantepfk",
            "gazisehirgaziantep": "LocalT1_gaziantepfk",
            "genclerbirligi": "LocalT1_genclerbirligiankara",
            "genclerbirligiankara": "LocalT1_genclerbirligiankara",
            "goztepe": "LocalT1_goztepe",
            "istanbulbasaksehir": "LocalT1_basaksehirfk",
            "karagumruk": "LocalT1_fatihkaragumruk",
            "kasimpasa": "LocalT1_kasimpasa",
            "kayserispor": "LocalT1_kayserispor",
            "kocaelispor": "LocalT1_kocaelispor",
            "konyaspor": "LocalT1_konyaspor",
            "rizespor": "LocalT1_caykurrizespor",
            "samsunspor": "LocalT1_samsunspor",
            "trabzonspor": "LocalT1_trabzonspor",
        ],
    ]

    private static func normalized(_ name: String) -> String {
        name.folding(
            options: [.diacriticInsensitive, .caseInsensitive],
            locale: Locale(identifier: "en_US_POSIX")
        ).filter { $0.isLetter || $0.isNumber }
    }

    static func assetName(teamName: String, league: String?) -> String? {
        guard let league else { return nil }
        return assetsByLeague[league]?[normalized(teamName)]
    }
}

@MainActor
final class BrandingStore: ObservableObject {
    static let shared = BrandingStore()
    @Published private var leagues: [LeagueBranding] = []

    private func normalized(_ name: String) -> String {
        name.folding(options: [.diacriticInsensitive, .caseInsensitive], locale: Locale(identifier: "en_US_POSIX"))
            .filter { $0.isLetter || $0.isNumber }
    }

    func teamURL(_ name: String, league: String?) -> URL? {
        let candidates = leagues.filter { league == nil || $0.code == league }
            .flatMap(\.teams).filter { team in team.names.contains { normalized($0) == normalized(name) } }
        // Never guess a crest when names identify different clubs.
        guard Set(candidates.map(\.id)).count == 1 else { return nil }
        return candidates.first?.logo
    }

    func load() async {
        do { leagues = try await APIClient.shared.branding() }
        catch { /* Preserve existing logos; neutral placeholders remain usable offline. */ }
    }
}

struct RemoteBadge: View {
    let url: URL?
    let label: String
    let size: CGFloat
    var body: some View {
        AsyncImage(url: url) { phase in
            if let image = phase.image {
                image.resizable().scaledToFit().padding(size * 0.1)
            } else {
                Image(systemName: "shield.lefthalf.filled")
                    .font(.system(size: size * 0.45, weight: .medium))
                    .foregroundStyle(Color.gray)
            }
        }
        .frame(width: size, height: size)
        .background(.white.opacity(0.95), in: RoundedRectangle(cornerRadius: size * 0.25))
        .accessibilityLabel(label)
    }
}

struct CrestBadge: View {
    let teamName: String
    var size: CGFloat = 44
    var league: String? = nil
    var logoURL: URL? = nil
    @ObservedObject private var branding = BrandingStore.shared

    @ViewBuilder
    var body: some View {
        if let assetName = LocalCrestCatalog.assetName(teamName: teamName, league: league) {
            Image(assetName)
                .resizable()
                .scaledToFit()
                .padding(size * 0.1)
                .frame(width: size, height: size)
                .background(.white.opacity(0.95), in: RoundedRectangle(cornerRadius: size * 0.25))
                .accessibilityLabel(teamName)
        } else {
            RemoteBadge(
                url: logoURL ?? branding.teamURL(teamName, league: league),
                label: teamName,
                size: size
            )
        }
    }
}

struct SmallCrest: View {
    let teamName: String
    var size: CGFloat = 20
    var league: String? = nil
    var logoURL: URL? = nil
    var body: some View { CrestBadge(teamName: teamName, size: size, league: league, logoURL: logoURL) }
}

struct LeagueBadge: View {
    let name: String
    var size: CGFloat = 28
    private var league: League? {
        League.allCases.first { $0.rawValue == name || $0.displayName == name }
    }
    var body: some View {
        RemoteBadge(url: league.map { URL(string: "https://media.api-sports.io/football/leagues/\($0.apiID).png")! },
                    label: league?.displayName ?? name, size: size)
    }
}

extension League {
    var apiID: Int {
        switch self {
        case .bundesliga: return 78
        case .premierLeague: return 39
        case .laLiga: return 140
        case .serieA: return 135
        case .ligue1: return 61
        case .superLig: return 203
        }
    }
}
