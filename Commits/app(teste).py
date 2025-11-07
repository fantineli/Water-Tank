from flask import Flask, render_template_string, send_file, Response, request, jsonify
from ftplib import FTP
import io
import traceback
import pandas as pd
import matplotlib # Matplotlib não é mais usado para os gráficos, mas pode ser mantido se você tiver outras dependências
from datetime import datetime, timedelta

# --- CONFIGURAÇÃO FTP (Sem alterações) ---
SERVIDOR_FTP = "10.100.100.157"
UTILIZADOR = "NeoOne"
SENHA = "Neo@123"
CAMINHO_DA_PASTA_FTP = "WT_HH"
NOME_DO_ARQUIVO_IMAGEM = "HH_LoRa_WTSCR.png"
NOME_DO_ARQUIVO_TXT = "HH_LoRa_WT.txt"

# --- FUNÇÃO DE CONVERSÃO (Sem alterações) ---
def converter_para_percentual(series_dados):
    min_mah = 4.0
    max_mah = 20.0
    percentual = (series_dados - min_mah) * 100 / (max_mah - min_mah)
    return percentual.clip(0, 100)

# --- CONTEÚDO HTML DA PÁGINA PRINCIPAL (Sem alterações) ---
HTML_PRINCIPAL = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WT HOPI HARI</title>
    <style>
        body { display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background-color: #f0f0f0; font-family: sans-serif; overflow: hidden; }
        .container { text-align: center; padding: 20px; border: 1px solid #ccc; background-color: #fff; box-shadow: 0 0 10px rgba(0,0,0,0.1); max-width: 95vw; max-height: 95vh; }
        img { max-width: 100%; max-height: calc(95vh - 120px); height: auto; border: 1px solid #ddd; display: block; }
        .info-bar { width: 100%; display: flex; justify-content: space-between; align-items: baseline; margin-top: 15px; }
        .info-left-group { display: flex; align-items: baseline; }
        .info-title { font-size: 1.1em; font-weight: bold; margin-right: 8px; }
        .info-timestamp { font-size: 0.9em; color: #555; }
        .button { background-color: #007bff; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <img id="imagemDinamica" src="/imagem" alt="Imagem carregada do storage da empresa">
        <div class="info-bar">
            <div class="info-left-group">
                <span class="info-title">WT HOPI HARI</span>
                <span id="timestamp-display" class="info-timestamp"></span>
            </div>
            <a href="/pagina-grafico" class="button">Ver Gráfico</a>
        </div>
    </div>
    <script>
        function atualizarConteudo() {
            var timestampElement = document.getElementById('timestamp-display');
            var dataHoraAtual = new Date().toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
            timestampElement.innerHTML = dataHoraAtual;
            var imgElement = document.getElementById('imagemDinamica');
            var timestamp = new Date().getTime();
            imgElement.src = '/imagem?cachebuster=' + timestamp;
        }
        atualizarConteudo();
        setInterval(atualizarConteudo, 5000);
    </script>
</body>
</html>
"""

# --- CONTEÚDO HTML DA PÁGINA DOS GRÁFICOS (Modificado para Plotly.js) ---
HTML_GRAFICO = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gráficos de Medições - WT HOPI HARI</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        * { box-sizing: border-box; }
        body {
            display: flex;
            flex-direction: column;
            align-items: center;
            height: 100vh;
            padding: 20px;
            margin: 0;
            background-color: #f0f0f0;
            font-family: sans-serif;
            overflow: hidden;
        }
        .header-container {
            width: 100%;
            max-width: 1800px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            flex-shrink: 0;
        }
        .button-voltar { background-color: #6c757d; color: white; padding: 8px 12px; text-decoration: none; border-radius: 5px; font-size: 0.9em; }
        .filter-container { text-align: right; }
        .filter-button { background-color: #fff; color: #333; padding: 8px 12px; font-size: 0.9em; border: 1px solid #ccc; border-radius: 5px; cursor: pointer; margin-left: 8px; }
        .filter-button.active { background-color: #007bff; color: white; border-color: #007bff; }
        
        .main-content {
            flex-grow: 1;
            display: flex;
            flex-direction: column; /* Altera para coluna para melhor responsividade em telas menores se necessário */
            gap: 20px;
            width: 100%;
            max-width: 1800px;
            min-height: 0;
        }
        .grafico-container {
            flex-grow: 1;
            display: flex;
            flex-direction: column;
            text-align: center;
            background-color: #fff;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
            min-height: 0;
        }
        .grafico-container h1 { margin-top: 0; margin-bottom: 10px; font-size: 1.1em; }
        
        /* 2. O grafico-wrapper agora contém o <div> do Plotly e o loader */
        .grafico-wrapper {
            position: relative;
            flex-grow: 1;
            width: 100%;
            height: 100%;
            min-height: 250px; /* Garante uma altura mínima */
        }
        /* O <div> do gráfico Plotly */
        .grafico-plotly {
            width: 100%;
            height: 100%;
        }
        
        .loader {
            border: 5px solid #f3f3f3;
            border-top: 5px solid #3498db;
            border-radius: 50%;
            width: 50px;
            height: 50px;
            animation: spin 1s linear infinite;
            position: absolute;
            top: 50%;
            left: 50%;
            margin-top: -25px;
            margin-left: -25px;
            z-index: 10;
            display: none; /* Começa escondido */
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="header-container">
        <a href="/" class="button-voltar">&larr; Voltar</a>
        <div class="filter-container">
            <button class="filter-button active" onclick="definirPeriodo('diario')">Diário</button>
            <button class="filter-button" onclick="definirPeriodo('semanal')">Semanal</button>
            <button class="filter-button" onclick="definirPeriodo('mensal')">Mensal</button>
        </div>
    </div>
    <div class="main-content">
        <div class="grafico-container">
            <h1 id="titulo-t1">Reservatório de Consumo 1</h1>
            <div class="grafico-wrapper">
                <div id="loader1" class="loader"></div>
                <div id="graficoTanque1" class="grafico-plotly"></div>
            </div>
        </div>
        <div class="grafico-container">
            <h1 id="titulo-t2">Reservatório de Consumo 2</h1>
            <div class="grafico-wrapper">
                <div id="loader2" class="loader"></div>
                <div id="graficoTanque2" class="grafico-plotly"></div>
            </div>
        </div>
    </div>
    <script>
        let periodoAtual = 'diario';
        
        function definirPeriodo(periodo) {
            periodoAtual = periodo;
            document.querySelectorAll('.filter-button').forEach(btn => btn.classList.remove('active'));
            document.querySelector(`button[onclick="definirPeriodo('${periodo}')"]`).classList.add('active');
            
            // Atualiza títulos
            const hoje = new Date();
            const dia = String(hoje.getDate()).padStart(2, '0');
            const mes = String(hoje.getMonth() + 1).padStart(2, '0');
            const ano = hoje.getFullYear();
            const dataFormatada = `${dia}/${mes}/${ano}`;

            const titulos = { 
                'diario': `Dia: ${dataFormatada}`, 
                'semanal': 'Últimos 7 Dias', 
                'mensal': 'Últimos 30 Dias' 
            };
            document.getElementById('titulo-t1').innerText = `Reservatório de Consumo 1 (${titulos[periodoAtual]})`;
            document.getElementById('titulo-t2').innerText = `Reservatório de Consumo 2 (${titulos[periodoAtual]})`;
            
            atualizarGraficos();
        }

        // 4. Nova função para atualizar os gráficos com Plotly
        async function atualizarGraficos() {
            const loader1 = document.getElementById('loader1');
            const loader2 = document.getElementById('loader2');
            const grafico1 = document.getElementById('graficoTanque1');
            const grafico2 = document.getElementById('graficoTanque2');

            // Mostra os loaders
            loader1.style.display = 'block';
            loader2.style.display = 'block';

            try {
                // Busca os dados da nova API
                const response = await fetch(`/api/dados-grafico?periodo=${periodoAtual}`);
                if (!response.ok) {
                    throw new Error(`Erro na API: ${response.statusText}`);
                }
                const dados = await response.json();

                if (dados.status === 'coletando') {
                    // Mostra mensagem de "Coletando dados"
                    Plotly.purge(grafico1); // Limpa gráfico anterior
                    Plotly.purge(grafico2);
                    grafico1.innerHTML = '<div style="display:flex; align-items:center; justify-content:center; height:100%; color:gray; font-size:18px;">Coletando dados para este período...</div>';
                    grafico2.innerHTML = '<div style="display:flex; align-items:center; justify-content:center; height:100%; color:gray; font-size:18px;">Coletando dados para este período...</div>';
                
                } else if (dados.timestamp && dados.timestamp.length > 0) {
                    // Prepara os dados para o Plotly
                    const trace1 = {
                        x: dados.timestamp,
                        y: dados.sensor1,
                        mode: 'lines+markers',
                        type: 'scatter',
                        marker: { size: 4 }
                    };
                    
                    const trace2 = {
                        x: dados.timestamp,
                        y: dados.sensor2,
                        mode: 'lines+markers',
                        type: 'scatter',
                        marker: { size: 4 }
                    };

                    // Configura o layout (eixo Y fixo como no original)
                    const layout = {
                        yaxis: {
                            range: [0, 105],
                            tickvals: [0, 20, 40, 50, 60, 80, 100],
                            title: 'Percentual (%)'
                        },
                        xaxis: {
                            title: 'Horário'
                        },
                        margin: { l: 50, r: 30, b: 50, t: 30 },
                        hovermode: 'x unified' // Melhora o tooltip
                    };
                    
                    // Configurações de responsividade
                    const config = { responsive: true };

                    // Desenha os gráficos
                    Plotly.react(grafico1, [trace1], layout, config);
                    Plotly.react(grafico2, [trace2], layout, config);
                
                } else {
                    // Caso de dados vazios
                    Plotly.purge(grafico1);
                    Plotly.purge(grafico2);
                    grafico1.innerHTML = '<div style="display:flex; align-items:center; justify-content:center; height:100%; color:gray; font-size:18px;">Sem dados disponíveis...</div>';
                    grafico2.innerHTML = '<div style="display:flex; align-items:center; justify-content:center; height:100%; color:gray; font-size:18px;">Sem dados disponíveis...</div>';
                }

            } catch (error) {
                console.error("Erro ao atualizar gráficos:", error);
                grafico1.innerHTML = `<div style="display:flex; align-items:center; justify-content:center; height:100%; color:red; font-size:14px;">Erro ao carregar dados: ${error.message}</div>`;
                grafico2.innerHTML = `<div style="display:flex; align-items:center; justify-content:center; height:100%; color:red; font-size:14px;">Erro ao carregar dados: ${error.message}</div>`;
            } finally {
                // Esconde os loaders
                loader1.style.display = 'none';
                loader2.style.display = 'none';
            }
        }
        
        // Carga inicial
        document.addEventListener('DOMContentLoaded', () => definirPeriodo('diario'));
        
        // Atualização periódica
        setInterval(atualizarGraficos, 300000); // 5 minutos
        
        // Redesenha os gráficos ao redimensionar a janela
        window.addEventListener('resize', () => {
             // Plotly.react lida bem com resize, mas podemos forçar um relayout se necessário
             // Apenas chamar 'atualizarGraficos' pode ser pesado (nova chamada de API)
             // Em vez disso, apenas redimensionamos
             Plotly.Plots.resize(document.getElementById('graficoTanque1'));
             Plotly.Plots.resize(document.getElementById('graficoTanque2'));
        });
    </script>
</body>
</html>
"""

# --- APLICAÇÃO WEB ---
app = Flask(__name__)

# --- FUNÇÃO AUXILIAR PARA LER OS DADOS (Sem alterações) ---
def obter_dados_do_ftp():
    ftp = None
    try:
        ftp = FTP(SERVIDOR_FTP)
        ftp.login(user=UTILIZADOR, passwd=SENHA)
        ftp.cwd(CAMINHO_DA_PASTA_FTP)
        dados_txt_em_memoria = io.BytesIO()
        ftp.retrbinary(f"RETR {NOME_DO_ARQUIVO_TXT}",
                       dados_txt_em_memoria.write)
        dados_txt_em_memoria.seek(0)

        df = pd.read_csv(dados_txt_em_memoria, header=None,
                         index_col=0, parse_dates=True)

        df.rename(columns={1: 'SENSOR 1', 2: 'SENSOR 2'}, inplace=True)
        return df
    finally:
        if ftp:
            ftp.quit()

# --- ROTAS DA PÁGINA (Sem alterações) ---
@app.route("/")
def pagina_principal():
    return render_template_string(HTML_PRINCIPAL)

@app.route("/imagem")
def servir_imagem():
    ftp = None
    try:
        ftp = FTP(SERVIDOR_FTP)
        ftp.login(user=UTILIZADOR, passwd=SENHA)
        ftp.cwd(CAMINHO_DA_PASTA_FTP)
        arquivo_em_memoria = io.BytesIO()
        ftp.retrbinary(f"RETR {NOME_DO_ARQUIVO_IMAGEM}",
                       arquivo_em_memoria.write)
        arquivo_em_memoria.seek(0)
        return send_file(arquivo_em_memoria, mimetype='image/png')
    except Exception as e:
        print(f"ERRO AO BUSCAR IMAGEM PRINCIPAL: {e}")
        return Response(f"Erro ao buscar imagem: {e}", status=500)
    finally:
        if ftp:
            ftp.quit()

@app.route("/pagina-grafico")
def pagina_grafico():
    return render_template_string(HTML_GRAFICO)


# --- NOVA ROTA DE API DE DADOS ---
# Esta rota substitui a antiga "/plot/<id>"
@app.route("/api/dados-grafico")
def api_dados_grafico():
    try:
        periodo = request.args.get('periodo', 'diario')
        df_completo = obter_dados_do_ftp()

        if df_completo.empty:
             return jsonify(timestamp=[], sensor1=[], sensor2=[])

        # Verifica se tem dados suficientes (mesma lógica sua)
        timespan_total = df_completo.index.max() - df_completo.index.min()
        mostrar_aviso = False
        if periodo == 'semanal' and timespan_total < timedelta(days=6):
            mostrar_aviso = True
        elif periodo == 'mensal' and timespan_total < timedelta(days=29):
            mostrar_aviso = True

        if mostrar_aviso:
            return jsonify(status='coletando')

        # Filtra o DataFrame (mesma lógica sua)
        agora = datetime.now()
        if periodo == 'diario':
            inicio_periodo = agora - timedelta(days=1)
            df = df_completo[df_completo.index >= inicio_periodo].copy()
        elif periodo == 'semanal':
            inicio_periodo = agora - timedelta(days=7)
            df = df_completo[df_completo.index >= inicio_periodo].copy()
        elif periodo == 'mensal':
            inicio_periodo = agora - timedelta(days=30)
            df = df_completo[df_completo.index >= inicio_periodo].copy()
        else:
            df = df_completo.copy()

        if df.empty:
            return jsonify(timestamp=[], sensor1=[], sensor2=[])
            
        # Converte os dados (ambas as colunas)
        df['SENSOR 1'] = converter_para_percentual(df['SENSOR 1'])
        df['SENSOR 2'] = converter_para_percentual(df['SENSOR 2'])
        
        # Formata os dados para JSON
        # Plotly.js lida bem com strings de data ISO
        df['timestamp_iso'] = df.index.strftime('%Y-%m-%dT%H:%M:%S')

        # Retorna o JSON que o JavaScript espera
        return jsonify(
            timestamp=df['timestamp_iso'].tolist(),
            sensor1=df['SENSOR 1'].tolist(),
            sensor2=df['SENSOR 2'].tolist()
        )

    except Exception as e:
        print(f"ERRO AO GERAR DADOS DA API: {e}")
        traceback.print_exc()
        # Retorna um erro em JSON para o frontend tratar
        return jsonify(error=str(e)), 500

# --- ROTA /plot REMOVIDA ---
# A rota @app.route("/plot/<int:tanque_id>") não é mais necessária

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) # Exemplo de como rodar