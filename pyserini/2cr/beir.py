#
# Pyserini: Reproducible IR research with sparse and dense representations
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import argparse
import math
import os
import time
import sys
from collections import defaultdict
from string import Template
import pkg_resources

import yaml

from ._base import run_eval_and_return_metric, ok_str, fail_str

trec_eval_metric_definitions = {
    'nDCG@10': '-c -m ndcg_cut.10',
    'R@100': '-c -m recall.100',
    'R@1000': '-c -m recall.1000'
}

beir_keys = ['trec-covid',
             'bioasq',
             'nfcorpus',
             'nq',
             'hotpotqa',
             'fiqa',
             'signal1m',
             'trec-news',
             'robust04',
             'arguana',
             'webis-touche2020',
             'cqadupstack-android',
             'cqadupstack-english',
             'cqadupstack-gaming',
             'cqadupstack-gis',
             'cqadupstack-mathematica',
             'cqadupstack-physics',
             'cqadupstack-programmers',
             'cqadupstack-stats',
             'cqadupstack-tex',
             'cqadupstack-unix',
             'cqadupstack-webmasters',
             'cqadupstack-wordpress',
             'quora',
             'dbpedia-entity',
             'scidocs',
             'fever',
             'climate-fever',
             'scifact'
             ]

def format_run_command(raw):
    return raw.replace('--topics', '\\\n  --topics')\
        .replace('--index', '\\\n  --index')\
        .replace('--encoder-class', '\\\n --encoder-class')\
        .replace('--output ', '\\\n  --output ')\
        .replace('--output-format trec', '\\\n  --output-format trec \\\n ') \
        .replace('--hits ', '\\\n  --hits ')


def format_eval_command(raw):
    return raw.replace('-c ', '\\\n  -c ')\
        .replace('run.', '\\\n  run.')


def read_file(f):
    fin = open(f, 'r')
    text = fin.read()
    fin.close()

    return text

def list_conditions(args):
    with open(pkg_resources.resource_filename(__name__, 'beir.yaml')) as f:
        yaml_data = yaml.safe_load(f)
        for condition in yaml_data['conditions']:
            print(condition['name'])
            
def list_datasets(args):
    for dataset in beir_keys:
        print(dataset)

def generate_report(args):
    table = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: 0.0)))
    commands = defaultdict(lambda: defaultdict(lambda: ''))
    eval_commands = defaultdict(lambda: defaultdict(lambda: ''))

    html_template = read_file(pkg_resources.resource_filename(__name__, 'beir_html.template'))
    row_template = read_file(pkg_resources.resource_filename(__name__, 'beir_html_row.template'))

    with open(pkg_resources.resource_filename(__name__, 'beir.yaml')) as f:
        yaml_data = yaml.safe_load(f)
        for condition in yaml_data['conditions']:
            name = condition['name']
            cmd_template = condition['command']

            for datasets in condition['datasets']:
                dataset = datasets['dataset']

                runfile = os.path.join(args.directory, f'run.beir.{name}.{dataset}.txt')
                cmd = Template(cmd_template).substitute(dataset=dataset, output=runfile)
                commands[dataset][name] = format_run_command(cmd)

                for expected in datasets['scores']:
                    for metric in expected:
                        eval_cmd = f'python -m pyserini.eval.trec_eval ' + \
                                   f'{trec_eval_metric_definitions[metric]} beir-v1.0.0-{dataset}-test {runfile}'
                        eval_commands[dataset][name] += format_eval_command(eval_cmd) + '\n\n'

                        table[dataset][name][metric] = expected[metric]

        row_cnt = 1
        html_rows = []
        for dataset in beir_keys:
            s = Template(row_template)
            s = s.substitute(row_cnt=row_cnt,
                             dataset=dataset,
                             s1=f'{table[dataset]["bm25-flat"]["nDCG@10"]:8.4f}',
                             s2=f'{table[dataset]["bm25-flat"]["R@100"]:8.4f}',
                             s3=f'{table[dataset]["bm25-multifield"]["nDCG@10"]:8.4f}',
                             s4=f'{table[dataset]["bm25-multifield"]["R@100"]:8.4f}',
                             s5=f'{table[dataset]["splade-distil-cocodenser-medium"]["nDCG@10"]:8.4f}',
                             s6=f'{table[dataset]["splade-distil-cocodenser-medium"]["R@100"]:8.4f}',
                             s7=f'{table[dataset]["contriever"]["nDCG@10"]:8.4f}',
                             s8=f'{table[dataset]["contriever"]["R@100"]:8.4f}',
                             s9=f'{table[dataset]["contriever-msmarco"]["nDCG@10"]:8.4f}',
                             s10=f'{table[dataset]["contriever-msmarco"]["R@100"]:8.4f}',
                             cmd1=commands[dataset]["bm25-flat"],
                             cmd2=commands[dataset]["bm25-multifield"],
                             cmd3=commands[dataset]["splade-distil-cocodenser-medium"],
                             cmd4=commands[dataset]["contriever"],
                             cmd5=commands[dataset]["contriever-msmarco"],
                             eval_cmd1=eval_commands[dataset]["bm25-flat"].rstrip(),
                             eval_cmd2=eval_commands[dataset]["bm25-multifield"].rstrip(),
                             eval_cmd3=eval_commands[dataset]["splade-distil-cocodenser-medium"].rstrip(),
                             eval_cmd4=eval_commands[dataset]["contriever"].rstrip(),
                             eval_cmd5=eval_commands[dataset]["contriever-msmarco"].rstrip(),
                             )

            html_rows.append(s)
            row_cnt += 1

        all_rows = '\n'.join(html_rows)
        with open(args.output, 'w') as out:
            out.write(Template(html_template).substitute(title='BEIR', rows=all_rows))

def run_conditions(args):
    start = time.time()

    table = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: 0.0)))

    with open(pkg_resources.resource_filename(__name__, 'beir.yaml')) as f:
        yaml_data = yaml.safe_load(f)
        for condition in yaml_data['conditions']:
            name = condition['name']
            cmd_template = condition['command']

            if args.all or args.condition == name:
                print(f'condition {name}:')
            else:
                continue

            for datasets in condition['datasets']:
                dataset = datasets['dataset']
                
                if args.all:
                    pass
                elif args.condition != name:
                    continue
                elif args.dataset and args.dataset != dataset:
                    continue

                print(f'  - dataset: {dataset}')

                runfile = os.path.join(args.directory, f'run.beir.{name}.{dataset}.txt')
                cmd = Template(cmd_template).substitute(dataset=dataset, output=runfile)
                
                if args.display_commands:
                    print(f'\n```bash\n{format_run_command(cmd)}\n```\n')

                if not os.path.exists(runfile):
                    if not args.dry_run:
                        os.system(cmd)

                for expected in datasets['scores']:
                    for metric in expected:
                        if not args.skip_eval:
                            if not os.path.exists(runfile):
                                continue
                            
                            score = float(run_eval_and_return_metric(metric, f'beir-v1.0.0-{dataset}-test',
                                                                     trec_eval_metric_definitions[metric], runfile))
                            result = ok_str if math.isclose(score, float(expected[metric])) \
                                else fail_str + f' expected {expected[metric]:.4f}'
                            print(f'      {metric:7}: {score:.4f} {result}')

                            table[dataset][name][metric] = score
                        else:
                            table[dataset][name][metric] = expected[metric]

            print('')

    models = ['bm25-flat', 'bm25-multifield', 'splade-distil-cocodenser-medium', 'contriever', 'contriever-msmarco']
    metrics = ['nDCG@10', 'R@100', 'R@1000']

    top_level_sums = defaultdict(lambda: defaultdict(float))
    cqadupstack_sums = defaultdict(lambda: defaultdict(float))
    final_scores = defaultdict(lambda: defaultdict(float))

    # Compute the running sums to compute the final mean scores
    for key in beir_keys:
        for model in models:
            for metric in metrics:
                if key.startswith('cqa'):
                    # The running sum for cqa needs to be kept separately.
                    cqadupstack_sums[model][metric] += table[key][model][metric]
                else:
                    top_level_sums[model][metric] += table[key][model][metric]

    # Compute the final mean
    for model in models:
        for metric in metrics:
            # Compute mean over cqa sub-collections first
            cqa_score = cqadupstack_sums[model][metric] / 12
            # Roll cqa scores into final overall mean
            final_score = (top_level_sums[model][metric] + cqa_score) / 18
            final_scores[model][metric] = final_score

    print(' ' * 30 + 'BM25-flat' + ' ' * 10 + 'BM25-mf' + ' ' * 13 + 'SPLADE' + ' ' * 11 + 'Contriever' + ' ' * 5 + 'Contriever-msmarco')
    print(' ' * 26 + 'nDCG@10   R@100    ' * 5)
    print(' ' * 27 + '-' * 14 + '     ' + '-' * 14 + '     ' + '-' * 14 + '     ' + '-' * 14 + '     ' + '-' * 14)
    for dataset in beir_keys:
        print(f'{dataset:25}' +
              f'{table[dataset]["bm25-flat"]["nDCG@10"]:8.4f}{table[dataset]["bm25-flat"]["R@100"]:8.4f}   ' +
              f'{table[dataset]["bm25-multifield"]["nDCG@10"]:8.4f}{table[dataset]["bm25-multifield"]["R@100"]:8.4f}   ' +
              f'{table[dataset]["splade-distil-cocodenser-medium"]["nDCG@10"]:8.4f}{table[dataset]["splade-distil-cocodenser-medium"]["R@100"]:8.4f}   ' + 
              f'{table[dataset]["contriever"]["nDCG@10"]:8.4f}{table[dataset]["contriever"]["R@100"]:8.4f}   ' + 
              f'{table[dataset]["contriever-msmarco"]["nDCG@10"]:8.4f}{table[dataset]["contriever-msmarco"]["R@100"]:8.4f}')
    print(' ' * 27 + '-' * 14 + '     ' + '-' * 14 + '     ' + '-' * 14 + '     ' + '-' * 14 + '     ' + '-' * 14)
    print('avg' + ' ' * 22 + f'{final_scores["bm25-flat"]["nDCG@10"]:8.4f}{final_scores["bm25-flat"]["R@100"]:8.4f}   ' +
            f'{final_scores["bm25-multifield"]["nDCG@10"]:8.4f}{final_scores["bm25-multifield"]["R@100"]:8.4f}   ' +
            f'{final_scores["splade-distil-cocodenser-medium"]["nDCG@10"]:8.4f}{final_scores["splade-distil-cocodenser-medium"]["R@100"]:8.4f}   ' + 
            f'{final_scores["contriever"]["nDCG@10"]:8.4f}{final_scores["contriever"]["R@100"]:8.4f}   ' +
            f'{final_scores["contriever-msmarco"]["nDCG@10"]:8.4f}{final_scores["contriever-msmarco"]["R@100"]:8.4f}')

    end = time.time()

    print('\n')
    print(f'Total elapsed time: {end - start:.0f}s')
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate regression matrix for BeIR corpora.')
    # To list all conditions/datasets
    parser.add_argument('--list-conditions', action='store_true', default=False, help='List available conditions.')
    parser.add_argument('--list-datasets', action='store_true', default=False, help='List available datasets.')
    # For generating reports
    parser.add_argument('--generate-report', action='store_true', default=False, help='Generate report.')
    parser.add_argument('--output', type=str, help='File to store report.', required=False)
    # For actually running the experimental conditions
    parser.add_argument('--all', action='store_true', default=False, help='Run all conditions.')
    parser.add_argument('--condition', type=str, help='Condition to run.', required=False)
    parser.add_argument('--dataset', type=str, help='Dataset to run.', required=False)
    parser.add_argument('--directory', type=str, help='Base directory.', default='', required=False)
    parser.add_argument('--dry-run', action='store_true', default=False, help='Print out commands but do not execute.')
    parser.add_argument('--skip-eval', action='store_true', default=False, help='Skip running trec_eval.')
    parser.add_argument('--display-commands', action='store_true', default=False, help='Display command.')
    args = parser.parse_args()

    if args.list_conditions:
        list_conditions(args)
        sys.exit()
    
    if args.list_datasets:
        list_datasets(args)
        sys.exit()

    if args.generate_report:
        if not args.output:
            print(f'Must specify report filename with --output.')
            sys.exit()

        generate_report(args)
        sys.exit()

    if not args.all and not args.condition:
        print(f'Must specify a specific condition using --condition or use --all to run all conditions.')
        sys.exit()
        
    if args.all and (args.condition or args.dataset):
        print('Specifying --all will run all conditions and datasets')
        sys.exit()

    run_conditions(args)
