"""
Extract text from AI Action Plan PDF submissions and write to Iceberg tables.

This script:
1. Reads PDF files from the data directory
2. Extracts text using PyMuPDF
3. Chunks the text for LLM processing
4. Writes to three separate Iceberg tables

Tables created:
- {schema}.ai_submissions_metadata: Document metadata (fast queries, no text)
- {schema}.ai_submissions_text: Full document text (join when needed)
- {schema}.ai_submissions_chunks: Text chunks for LLM processing

Environment variables required:
- SCHEMA: Target schema/namespace for tables
- AWS_ACCESS_KEY_ID: AWS access key
- AWS_SECRET_ACCESS_KEY: AWS secret key
- AWS_DEFAULT_REGION: AWS region (default: us-west-2)
- AWS_S3_BUCKET_TABULAR: S3 bucket for Iceberg warehouse
"""

import sys
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF
import pyarrow as pa
from pyiceberg.catalog import load_catalog
from pyiceberg.schema import Schema
from pyiceberg.types import (
    IntegerType,
    LongType,
    StringType,
    TimestampType,
    NestedField
)
import boto3
from dotenv import load_dotenv

# Add parent directory to path for config import
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import get_pdf_filter_names, classify_submitter_type


# Configure logging for DAG consumption
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PDFExtractionError(Exception):
    """Raised when PDF extraction fails."""
    pass


class IcebergWriteError(Exception):
    """Raised when writing to Iceberg fails."""
    pass


class ConfigurationError(Exception):
    """Raised when required configuration is missing."""
    pass


def get_required_env(var_name: str) -> str:
    """Get required environment variable or raise ConfigurationError."""
    value = os.environ.get(var_name)
    if not value:
        raise ConfigurationError(f"Required environment variable {var_name} is not set")
    return value


def get_table_names() -> tuple[str, str, str]:
    """Get table names from SCHEMA environment variable.

    Returns:
        tuple: (metadata_table, text_table, chunks_table)
    """
    schema = get_required_env('SCHEMA')
    return (
        f"{schema}.ai_submissions_metadata",
        f"{schema}.ai_submissions_text",
        f"{schema}.ai_submissions_chunks"
    )


def extract_text_from_pdf(pdf_path: str) -> tuple[str, int]:
    """Extract all text from a PDF file.

    Args:
        pdf_path: Path to PDF file

    Returns:
        tuple: (full_text, page_count)

    Raises:
        PDFExtractionError: If extraction fails
    """
    try:
        doc = fitz.open(pdf_path)
        full_text = ""
        for page in doc:
            full_text += page.get_text() + "\n"
        page_count = len(doc)
        doc.close()
        return full_text, page_count
    except Exception as e:
        raise PDFExtractionError(f"Failed to extract text from {pdf_path}: {e}")


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """Split text into overlapping chunks.

    Args:
        text: Full document text
        chunk_size: Target words per chunk
        overlap: Words to overlap between chunks

    Returns:
        List of text chunks
    """
    words = text.split()
    if len(words) <= chunk_size:
        return [text] if text.strip() else []

    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start = end - overlap

    return chunks


def parse_submitter_from_filename(filename: str) -> tuple[str, str]:
    """Extract submitter name and type from filename.

    Args:
        filename: PDF filename (e.g., 'OpenAI-RFI-2025.pdf', 'AI-RFI-2025-0829.pdf')

    Returns:
        tuple: (submitter_name, submitter_type)
    """
    # Remove extension and common suffixes
    name = filename.replace('.pdf', '').replace('-RFI-2025', '').replace('-AI-RFI-2025', '')

    # Use shared config for classification
    submitter_type = classify_submitter_type(name)
    return name, submitter_type


def get_catalog():
    """Initialize and return PyIceberg catalog.

    Returns:
        Iceberg catalog configured for AWS Glue

    Raises:
        ConfigurationError: If required env vars are missing
    """
    aws_region = os.environ.get('AWS_DEFAULT_REGION', 'us-west-2')
    s3_bucket = get_required_env('AWS_S3_BUCKET_TABULAR')

    # Ensure AWS credentials are set
    get_required_env('AWS_ACCESS_KEY_ID')
    get_required_env('AWS_SECRET_ACCESS_KEY')

    boto3.setup_default_session(region_name=aws_region)

    return load_catalog(
        name="glue_catalog",
        **{
            "type": "glue",
            "region": aws_region,
            "warehouse": f"s3://{s3_bucket}/iceberg-warehouse/",
        }
    )


def extract_pdf_submissions(
    pdf_dir: str = "data/90-fr-9088-combined-responses",
    limit: Optional[int] = None,
    priority_only: bool = False,
) -> dict:
    """
    Extract text from PDF submissions and write to Iceberg tables.

    Args:
        pdf_dir: Directory containing PDF files
        limit: Max number of PDFs to process (None = all)
        priority_only: If True, only process key company submissions

    Returns:
        dict with keys: documents, chunks, errors, tables

    Raises:
        ConfigurationError: If required environment variables are missing
        IcebergWriteError: If writing to Iceberg fails
    """
    # Get table names from environment
    table_metadata, table_text, table_chunks = get_table_names()
    logger.info(f"Target tables: {table_metadata}, {table_text}, {table_chunks}")

    # Initialize catalog
    catalog = get_catalog()
    logger.info("Initialized Iceberg catalog")

    # Priority companies from shared config
    priority_companies = get_pdf_filter_names()

    # Get list of PDF files
    pdf_path = Path(pdf_dir)
    if not pdf_path.exists():
        raise ConfigurationError(f"PDF directory not found: {pdf_dir}")

    pdf_files = list(pdf_path.glob("*.pdf"))
    logger.info(f"Found {len(pdf_files)} PDF files")

    # Filter to priority companies if requested
    if priority_only:
        pdf_files = [
            f for f in pdf_files
            if any(p.lower() in f.name.lower() for p in priority_companies)
        ]
        logger.info(f"Filtered to {len(pdf_files)} priority company submissions")

    # Apply limit
    if limit:
        pdf_files = pdf_files[:limit]
        logger.info(f"Limited to {len(pdf_files)} files")

    # Process PDFs into three separate record lists
    metadata_records = []
    text_records = []
    chunk_records = []
    errors = []
    processed_at = datetime.now()

    for i, pdf_file in enumerate(pdf_files):
        try:
            # Extract text
            full_text, page_count = extract_text_from_pdf(str(pdf_file))
            word_count = len(full_text.split())

            # Parse submitter info
            submitter_name, submitter_type = parse_submitter_from_filename(pdf_file.name)

            # Create document ID
            doc_id = pdf_file.stem  # filename without extension

            # Metadata record (no text - fast to query)
            metadata_records.append({
                'document_id': doc_id,
                'filename': pdf_file.name,
                'submitter_name': submitter_name,
                'submitter_type': submitter_type,
                'page_count': page_count,
                'word_count': word_count,
                'file_size_bytes': pdf_file.stat().st_size,
                'processed_at': processed_at
            })

            # Text record (full text - join when needed)
            text_records.append({
                'document_id': doc_id,
                'full_text': full_text,
                'processed_at': processed_at
            })

            # Chunk records (for LLM processing)
            chunks = chunk_text(full_text)
            for chunk_idx, chunk_text_content in enumerate(chunks):
                chunk_records.append({
                    'chunk_id': f"{doc_id}_{chunk_idx}",
                    'document_id': doc_id,
                    'chunk_index': chunk_idx,
                    'total_chunks': len(chunks),
                    'chunk_text': chunk_text_content,
                    'word_count': len(chunk_text_content.split()),
                    'processed_at': processed_at
                })

            if (i + 1) % 10 == 0:
                logger.info(f"Processed {i + 1}/{len(pdf_files)} files...")

        except PDFExtractionError as e:
            error_msg = str(e)
            logger.warning(error_msg)
            errors.append({'file': pdf_file.name, 'error': error_msg})
            continue
        except Exception as e:
            error_msg = f"Unexpected error processing {pdf_file.name}: {e}"
            logger.error(error_msg)
            errors.append({'file': pdf_file.name, 'error': error_msg})
            continue

    logger.info(f"Extracted {len(metadata_records)} documents with {len(chunk_records)} chunks")
    if errors:
        logger.warning(f"Encountered {len(errors)} errors during extraction")

    # Don't proceed if no records extracted
    if not metadata_records:
        raise PDFExtractionError("No documents were successfully extracted")

    # Define Iceberg schemas
    metadata_schema = Schema(
        NestedField(1, "document_id", StringType(), required=True),
        NestedField(2, "filename", StringType(), required=False),
        NestedField(3, "submitter_name", StringType(), required=False),
        NestedField(4, "submitter_type", StringType(), required=False),
        NestedField(5, "page_count", IntegerType(), required=False),
        NestedField(6, "word_count", IntegerType(), required=False),
        NestedField(7, "file_size_bytes", LongType(), required=False),
        NestedField(8, "processed_at", TimestampType(), required=False)
    )

    text_schema = Schema(
        NestedField(1, "document_id", StringType(), required=True),
        NestedField(2, "full_text", StringType(), required=False),
        NestedField(3, "processed_at", TimestampType(), required=False)
    )

    chunks_schema = Schema(
        NestedField(1, "chunk_id", StringType(), required=True),
        NestedField(2, "document_id", StringType(), required=False),
        NestedField(3, "chunk_index", IntegerType(), required=False),
        NestedField(4, "total_chunks", IntegerType(), required=False),
        NestedField(5, "chunk_text", StringType(), required=False),
        NestedField(6, "word_count", IntegerType(), required=False),
        NestedField(7, "processed_at", TimestampType(), required=False)
    )

    # PyArrow schemas
    pa_metadata_schema = pa.schema([
        pa.field('document_id', pa.string(), nullable=False),
        pa.field('filename', pa.string(), nullable=True),
        pa.field('submitter_name', pa.string(), nullable=True),
        pa.field('submitter_type', pa.string(), nullable=True),
        pa.field('page_count', pa.int32(), nullable=True),
        pa.field('word_count', pa.int32(), nullable=True),
        pa.field('file_size_bytes', pa.int64(), nullable=True),
        pa.field('processed_at', pa.timestamp('us'), nullable=True)
    ])

    pa_text_schema = pa.schema([
        pa.field('document_id', pa.string(), nullable=False),
        pa.field('full_text', pa.string(), nullable=True),
        pa.field('processed_at', pa.timestamp('us'), nullable=True)
    ])

    pa_chunks_schema = pa.schema([
        pa.field('chunk_id', pa.string(), nullable=False),
        pa.field('document_id', pa.string(), nullable=True),
        pa.field('chunk_index', pa.int32(), nullable=True),
        pa.field('total_chunks', pa.int32(), nullable=True),
        pa.field('chunk_text', pa.string(), nullable=True),
        pa.field('word_count', pa.int32(), nullable=True),
        pa.field('processed_at', pa.timestamp('us'), nullable=True)
    ])

    # Convert to PyArrow tables
    pa_metadata_table = pa.Table.from_pylist(metadata_records, schema=pa_metadata_schema)
    pa_text_table = pa.Table.from_pylist(text_records, schema=pa_text_schema)
    pa_chunks_table = pa.Table.from_pylist(chunk_records, schema=pa_chunks_schema)

    # Write to Iceberg
    try:
        # Helper to create or load table
        def get_or_create_table(table_name, schema):
            try:
                table = catalog.load_table(table_name)
                logger.info(f"Table {table_name} already exists")
                return table
            except Exception:
                table = catalog.create_table(identifier=table_name, schema=schema)
                logger.info(f"Created table {table_name}")
                return table

        # Create/load all tables
        iceberg_metadata = get_or_create_table(table_metadata, metadata_schema)
        iceberg_text = get_or_create_table(table_text, text_schema)
        iceberg_chunks = get_or_create_table(table_chunks, chunks_schema)

        # Write data
        iceberg_metadata.overwrite(pa_metadata_table)
        iceberg_text.overwrite(pa_text_table)
        iceberg_chunks.overwrite(pa_chunks_table)

        logger.info(f"Successfully wrote {len(metadata_records)} documents to {table_metadata}")
        logger.info(f"Successfully wrote {len(text_records)} text records to {table_text}")
        logger.info(f"Successfully wrote {len(chunk_records)} chunks to {table_chunks}")

    except Exception as e:
        raise IcebergWriteError(f"Failed to write to Iceberg: {e}")

    return {
        'documents': len(metadata_records),
        'chunks': len(chunk_records),
        'errors': errors,
        'tables': {
            'metadata': table_metadata,
            'text': table_text,
            'chunks': table_chunks
        }
    }


if __name__ == "__main__":
    load_dotenv()

    # Parse command line args
    pdf_dir = sys.argv[1] if len(sys.argv) > 1 else "data/90-fr-9088-combined-responses"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
    priority_only = sys.argv[3].lower() == 'true' if len(sys.argv) > 3 else False

    try:
        result = extract_pdf_submissions(
            pdf_dir=pdf_dir,
            limit=limit,
            priority_only=priority_only
        )
        logger.info(f"Extraction complete: {result}")
    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except PDFExtractionError as e:
        logger.error(f"PDF extraction error: {e}")
        sys.exit(1)
    except IcebergWriteError as e:
        logger.error(f"Iceberg write error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
