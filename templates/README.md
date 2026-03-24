# Templates

Ce dossier contient les templates DOCX pour l'export des devis.

## devis_template.docx

Template DOCX utilisé par `docxtpl` pour générer les devis.

Si ce fichier n'existe pas, l'application en créera un minimal automatiquement lors du premier export DOCX.

### Variables disponibles dans le template

- `numero` : Numéro du devis
- `date` : Date du devis (format: DD/MM/YYYY)
- `validite` : Validité en jours
- `reference_affaire` : Référence affaire
- `client_nom` : Nom du client
- `client_adresse` : Adresse du client
- `client_cp_ville` : Code postal et ville du client
- `client_telephone` : Téléphone du client
- `client_email` : Email du client
- `chantier_adresse` : Adresse du chantier
- `chantier_cp_ville` : Code postal et ville du chantier
- `modalites_paiement` : Modalités de paiement
- `delais` : Délais
- `remarques` : Remarques
- `lots` : Liste des lots (voir structure ci-dessous)
- `total_ht` : Total HT
- `total_tva` : Total TVA
- `total_ttc` : Total TTC

### Structure des lots

```jinja2
{% for lot in lots %}
  {{ lot.nom }}
  {% for ligne in lot.lignes %}
    {{ ligne.designation }} - Qté: {{ ligne.quantite }} {{ ligne.unite }} - PU: {{ ligne.prix_unitaire }} € - Total: {{ ligne.total_ht }} €
  {% endfor %}
  Sous-total: {{ lot.sous_total }} €
{% endfor %}
```
