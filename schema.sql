-- =====================================================================
-- schema.sql
-- Sistema de Ordens de Serviço para assistência técnica de computadores
-- SGBD alvo: PostgreSQL (12 ou superior)
--
-- Modelagem:
--   clientes (1) ────< (N) ordens_servico
--   Um mesmo cliente pode abrir várias ordens de serviço ao longo do
--   tempo, uma para cada equipamento/atendimento.
-- =====================================================================


-- ---------------------------------------------------------------------
-- BLOCO 1: Limpeza
-- Remove os objetos caso já existam, permitindo reexecutar o script do
-- zero. A tabela filha (ordens_servico) é removida antes da tabela pai
-- (clientes) para não violar a chave estrangeira.
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS ordens_servico;
DROP TABLE IF EXISTS clientes;
DROP FUNCTION IF EXISTS fn_atualiza_data_atualizacao();


-- ---------------------------------------------------------------------
-- BLOCO 2: Tabela CLIENTES
-- Armazena os dados cadastrais de cada cliente.
--   - id: chave primária gerada automaticamente.
--   - nome, email e celular_whatsapp são obrigatórios (NOT NULL).
--   - email é único: não pode haver dois clientes com o mesmo e-mail.
--   - data_cadastro recebe a data/hora atual por padrão.
-- ---------------------------------------------------------------------
CREATE TABLE clientes (
    id                INTEGER      GENERATED ALWAYS AS IDENTITY,
    nome              VARCHAR(150) NOT NULL,
    endereco          VARCHAR(255),
    email             VARCHAR(255) NOT NULL,
    celular_whatsapp  VARCHAR(13)  NOT NULL,
    data_cadastro     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Chave primária
    CONSTRAINT pk_clientes PRIMARY KEY (id),

    -- E-mail único
    CONSTRAINT uq_clientes_email UNIQUE (email),

    -- Nome não pode ser apenas espaços em branco
    CONSTRAINT ck_clientes_nome_nao_vazio CHECK (TRIM(nome) <> ''),

    -- Validação simples do formato do e-mail: texto@dominio.ext
    CONSTRAINT ck_clientes_email_formato
        CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'),

    -- Celular: somente dígitos, entre 10 e 13 caracteres
    -- (ex.: 11987654321 ou 5511987654321)
    CONSTRAINT ck_clientes_celular_formato
        CHECK (celular_whatsapp ~ '^[0-9]{10,13}$')
);


-- ---------------------------------------------------------------------
-- BLOCO 3: Tabela ORDENS_SERVICO
-- Cada registro representa um equipamento entregue para reparo.
--   - cliente_id referencia clientes(id) (chave estrangeira).
--   - status só aceita os valores definidos no CHECK e começa como
--     'Aberto'.
--   - data_abertura recebe a data/hora atual por padrão.
--   - data_atualizacao é mantida automaticamente por trigger (Bloco 5).
--
-- Comportamento na exclusão (ON DELETE RESTRICT):
--   Um cliente que possui ordens de serviço NÃO pode ser excluído. Isso
--   preserva o histórico de atendimentos; para remover o cliente é
--   preciso antes tratar (excluir/arquivar) as suas ordens.
-- Comportamento na atualização (ON UPDATE CASCADE):
--   Se o id do cliente mudar, as ordens acompanham a alteração.
-- ---------------------------------------------------------------------
CREATE TABLE ordens_servico (
    id                 INTEGER      GENERATED ALWAYS AS IDENTITY,
    cliente_id         INTEGER      NOT NULL,
    modelo_computador  VARCHAR(150) NOT NULL,
    problema_relatado  TEXT         NOT NULL,
    status             VARCHAR(20)  NOT NULL DEFAULT 'Aberto',
    data_abertura      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    data_atualizacao   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Chave primária
    CONSTRAINT pk_ordens_servico PRIMARY KEY (id),

    -- Chave estrangeira para clientes, com comportamento de exclusão
    CONSTRAINT fk_ordens_servico_cliente
        FOREIGN KEY (cliente_id) REFERENCES clientes (id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,

    -- Status permitido apenas dentro da lista definida
    CONSTRAINT ck_ordens_servico_status
        CHECK (status IN ('Aberto', 'Em análise', 'Aguardando peça',
                          'Concluído', 'Entregue')),

    -- Campos de texto obrigatórios não podem ser apenas espaços
    CONSTRAINT ck_ordens_servico_modelo_nao_vazio
        CHECK (TRIM(modelo_computador) <> ''),
    CONSTRAINT ck_ordens_servico_problema_nao_vazio
        CHECK (TRIM(problema_relatado) <> ''),

    -- A última atualização não pode ser anterior à abertura
    CONSTRAINT ck_ordens_servico_datas
        CHECK (data_atualizacao >= data_abertura)
);


-- ---------------------------------------------------------------------
-- BLOCO 4: Índices
-- Acelera as consultas mais comuns: listar as ordens de um cliente e
-- filtrar ordens por status. (O e-mail já possui índice por ser UNIQUE.)
-- ---------------------------------------------------------------------
CREATE INDEX idx_ordens_servico_cliente_id ON ordens_servico (cliente_id);
CREATE INDEX idx_ordens_servico_status     ON ordens_servico (status);


-- ---------------------------------------------------------------------
-- BLOCO 5: Atualização automática de data_atualizacao
-- Função + trigger que gravam a data/hora atual em data_atualizacao
-- sempre que uma ordem de serviço for alterada (ex.: mudança de status).
-- ---------------------------------------------------------------------
CREATE FUNCTION fn_atualiza_data_atualizacao()
RETURNS TRIGGER AS $$
BEGIN
    NEW.data_atualizacao := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_ordens_servico_data_atualizacao
    BEFORE UPDATE ON ordens_servico
    FOR EACH ROW
    EXECUTE FUNCTION fn_atualiza_data_atualizacao();


-- ---------------------------------------------------------------------
-- BLOCO 6: Dados de exemplo (opcional)
-- Demonstra um cliente com mais de um equipamento ao longo do tempo.
-- Pode ser removido em ambiente de produção.
-- ---------------------------------------------------------------------
INSERT INTO clientes (nome, endereco, email, celular_whatsapp) VALUES
    ('Maria Souza',  'Rua das Flores, 100 - São Paulo/SP', 'maria.souza@email.com', '11987654321'),
    ('João Pereira', 'Av. Brasil, 2500 - Rio de Janeiro/RJ', 'joao.pereira@email.com', '5521998765432');

INSERT INTO ordens_servico (cliente_id, modelo_computador, problema_relatado, status) VALUES
    (1, 'Dell Inspiron 15 3520', 'Notebook não liga.',                     'Em análise'),
    (1, 'Lenovo IdeaCentre 3',   'Computador muito lento e travando.',     'Aberto'),
    (2, 'Acer Aspire 5',         'Tela piscando e com listras verticais.', 'Aguardando peça');
