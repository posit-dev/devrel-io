import polars as pl

# Read the blog posts CSV
df = pl.read_csv('data/input/posit-blog-posts.csv')

# Project keywords mapping from config.toml
def determine_project(title: str, categories: str, tags: str) -> str:
    """Determine the project based on title, categories, and tags."""
    # Combine all text sources
    text = f"{title} {categories} {tags}".lower()

    # Check for specific projects
    # More specific matches first
    if 'shiny for python' in text or 'py-shiny' in text or 'shinychat' in text:
        return 'shiny-python'
    if 'shiny for r' in text or 'bslib' in text:
        return 'shiny-r'
    if 'great tables' in text or 'great_tables' in text:
        return 'great-tables'
    if '{gt}' in text or ' gt ' in text:
        return 'gt'
    if 'pointblank' in text and 'python' in text:
        return 'pointblank-python'
    if 'pointblank' in text:
        return 'pointblank-r'
    if 'orbital' in text and ('scikit-learn' in text or 'python' in text):
        return 'orbital-python'
    if 'orbital' in text and ('tidymodels' in text or ' r ' in text):
        return 'orbital-r'
    if 'quarto' in text:
        return 'quarto'
    if 'positron' in text:
        return 'positron'
    if 'plotnine' in text:
        return 'plotnine'
    if 'chatlas' in text:
        return 'chatlas'
    if 'ellmer' in text:
        return 'ellmer'
    if 'databot' in text:
        return 'databot'
    if 'air' in text and 'language server' in text:
        return 'air'
    if 'publisher' in text:
        return 'publisher'
    if 'shinyuieditor' in text:
        return 'shinyuieditor'
    if 'ggplot2' in text:
        return 'ggplot2'
    if 'dplyr' in text:
        return 'dplyr'
    if 'tidyverse' in text or 'tidymodels' in text:
        return 'tidyverse'
    if 'shiny' in text:
        # Generic shiny - try to determine from URL or context
        return 'shiny-python' if 'python' in text else 'shiny-r'

    # Additional sensible mappings for common topics
    if 'gradio' in text:
        return 'posit-connect'
    if 'chronicle' in text:
        return 'posit-chronicle'
    if 'connect cloud' in text or 'posit connect cloud' in text:
        return 'connect-cloud'
    if 'posit connect' in text and 'connect cloud' not in text:
        return 'posit-connect'
    if 'posit workbench' in text or 'rstudio ide' in text:
        return 'posit-workbench'
    if 'posit package manager' in text:
        return 'posit-package-manager'
    if 'posit team' in text:
        return 'posit-team'

    # If no match found, return empty string
    return ''

# Create the new dataframe with the required columns
new_df = df.select([
    # Convert Published Date to datetime format (matching inputs.csv format)
    pl.col('Published Date').str.to_datetime().dt.strftime('%Y-%m-%d %H:%M:%S').alias('datetime'),

    # Determine project using map_elements
    pl.struct(['Title', 'Categories', 'Tags'])
      .map_elements(
          lambda row: determine_project(
              str(row['Title']),
              str(row['Categories']),
              str(row['Tags'])
          ),
          return_dtype=pl.String
      )
      .alias('project'),

    # Set type to 'blog' for all entries
    pl.lit('blog').alias('type'),

    # Copy title and URL
    pl.col('Title').alias('title'),

    # Empty author and notes
    pl.lit('').alias('author'),
    pl.col('URL').alias('url'),
    pl.lit('').alias('notes'),
])

# Write to data/input/blogs.csv
new_df.write_csv('data/input/blogs.csv')

print(f"Processed {len(new_df)} blog posts")
print(f"\nProject distribution:")
print(new_df.group_by('project').agg(pl.count()).sort('count', descending=True))
print(f"\nEntries without project: {new_df.filter(pl.col('project') == '').shape[0]}")
