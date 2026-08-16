# -*- coding: utf-8 -*-
# Part of CRM Executive Dashboard. See LICENSE file for full copyright and licensing details.

"""
Chart data post-processors.

The KPI engine returns chart data in a generic
``{'labels': [...], 'datasets': [...]}`` shape. The frontend uses
Chart.js, which expects that shape directly, but we add a few
enhancements here:

  * Inject brand-palette colours so each dataset renders in
    navy/gold without the JS needing to know the palette.
  * Compute derived metrics (e.g. moving average for revenue trend)
    that the KPI engine does not pre-compute.
  * Return Chart.js options (legend position, animation duration) so
    the JS can render with one call.

This module is *purely additive*: it consumes the engine output and
returns a dict that the controller forwards verbatim to the page. The
engine itself is untouched.
"""

import logging

_logger = logging.getLogger(__name__)

# Brand palette (must match static/src/css/crm_dashboard_variables.css)
PALETTE = {
    'navy_dark': '#0B1F3A',
    'navy_deep': '#13294B',
    'ivory': '#F8F4EA',
    'white': '#FFFFFF',
    'gold_light': '#D8C08C',
    'gold_bronze': '#A37C27',
    'success': '#198754',
    'warning': '#FFC107',
    'danger': '#DC3545',
}

CHART_COLORS = [
    PALETTE['gold_bronze'],
    PALETTE['navy_deep'],
    PALETTE['gold_light'],
    PALETTE['success'],
    PALETTE['warning'],
    PALETTE['danger'],
    PALETTE['navy_dark'],
]

DEFAULT_OPTIONS = {
    'responsive': True,
    'maintainAspectRatio': False,
    'animation': {'duration': 600},
    'plugins': {
        'legend': {'position': 'top', 'labels': {'boxWidth': 12}},
        'tooltip': {'enabled': True},
    },
}


def colorize(charts):
    """Return a copy of the charts dict with dataset colours injected.

    Modifies a deep copy — original engine output is untouched.
    """
    out = {}
    for chart_name, chart_data in charts.items():
        if not isinstance(chart_data, dict) or 'datasets' not in chart_data:
            # Custom shapes (funnel, pipeline_aging) handled per-case
            out[chart_name] = dict(chart_data)
            continue
        new = dict(chart_data)
        new_datasets = []
        for idx, ds in enumerate(chart_data['datasets']):
            ds = dict(ds)
            ds['backgroundColor'] = CHART_COLORS[idx % len(CHART_COLORS)] + '33'  # 20% alpha
            ds['borderColor'] = CHART_COLORS[idx % len(CHART_COLORS)]
            ds['borderWidth'] = 2
            ds['fill'] = idx == 0  # only first dataset is filled
            ds['tension'] = 0.3
            new_datasets.append(ds)
        new['datasets'] = new_datasets
        new['options'] = DEFAULT_OPTIONS
        out[chart_name] = new
    return out


def add_moving_average(chart_data, window=7):
    """Append a 7-day moving average to the revenue trend chart.

    Returns a *new* dict (does not mutate input). The frontend will see
    an extra dataset alongside the raw revenue series.
    """
    import copy
    out = copy.deepcopy(chart_data)
    rev = out.get('revenue_trend')
    if not rev or not rev.get('datasets'):
        return out
    raw = rev['datasets'][0]['data']
    if len(raw) < window:
        return out
    ma = []
    for i in range(len(raw)):
        if i < window - 1:
            ma.append(None)
        else:
            ma.append(sum(raw[i - window + 1:i + 1]) / window)
    rev['datasets'].append({
        'label': f'{window}-day MA',
        'data': ma,
        'borderColor': PALETTE['gold_bronze'],
        'backgroundColor': PALETTE['gold_bronze'] + '22',
        'borderWidth': 2,
        'borderDash': [5, 5],
        'fill': False,
        'tension': 0.4,
    })
    out['revenue_trend'] = rev
    return out


def funnel_to_hbar(funnel_chart):
    """Convert the funnel ``{labels, data, values}`` into a horizontal
    bar chart that Chart.js can render directly. Two datasets: count
    and value.
    """
    return {
        'labels': funnel_chart.get('labels', []),
        'datasets': [
            {
                'label': 'Count',
                'data': funnel_chart.get('data', []),
                'backgroundColor': PALETTE['gold_bronze'] + '88',
                'borderColor': PALETTE['gold_bronze'],
                'borderWidth': 1,
            },
        ],
        'options': {
            **DEFAULT_OPTIONS,
            'indexAxis': 'y',
        },
    }


def process(charts):
    """Run all post-processors. Entry point called by the controller."""
    try:
        charts = colorize(charts)
        charts = add_moving_average(charts, window=7)
        if 'funnel' in charts:
            charts['funnel'] = funnel_to_hbar(charts['funnel'])
        return charts
    except Exception as e:
        _logger.exception("CED: chart post-processing failed: %s", e)
        # Never break the page on chart enrichment failure — return
        # the raw charts from the engine.
        return charts
